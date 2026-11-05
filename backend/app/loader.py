"""Daily Adobe Real-Time CDP profile export -> Couchbase + AOM Knowledge Base.

Run by the backend on startup and every RTCDP_POLL_SECONDS (it only does work
when a newer `exportTime=YYYYMMDD/_SUCCESS` partition lands), or by hand:

    python -m app.loader [--export-dir PATH] [--force] [--no-kb]

1. Stream every JSON Lines part file of the newest complete partition - the
   Real-Time CDP dataset export of `guest_profile_personalization`
   (adobe/rtcdp/README.md).
2. Upsert one `profiles` document per guest (all ~100MB in Couchbase
   mode). Live state the guest changed since the last export (stateroom moves,
   check-in, purchases) is carried forward - in production that state would
   already be in the next day's profile.
3. Index bookings for login, publish the catalog, re-rank offers for guests
   inside the planning window.
4. Publish to the AOM Knowledge Base: the Guest Services Playbook, rendered
   from the AEM content fragments (adobe/aem/README.md), and one profile
   document per guest sailing within KB_WINDOW_DAYS (demo personas always),
   replacing yesterday's version of each. The concierge's AOM RAG Application
   is then re-scoped to the new playbook document.

Context caches need no sweep: every cached context records the export date it
was built from, so the new export makes them all stale at once.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import glob
import hashlib
import json
import logging
import os
import time

from . import catalog as C
from . import adobe, config, knowledge, personalization, rag_app
from .aom_client import AOMError, aom
from .docs import CATALOG_CHANNEL, CATALOG_ID, STATE, guest_channel, now_iso, profile_id
from .store import store

log = logging.getLogger("pcl.loader")
PERSONAS = ["G00000101", "G00000201", "G00000301"]
LIVE_FIELDS_RES = ("stateroom", "checkin_status", "arrival_slot", "upgrade_history")
STATUS = {"state": "idle"}
_TASKS: list = []  # keep a reference so background KB publishing is not garbage-collected


PARTITION_PREFIX = "exportTime="


def partition_date(partition: str) -> str:
    """exportTime=20261104[HHMMSS] -> 2026-11-04 (dt=2026-11-04 from older exports still works)."""
    stamp = os.path.basename(partition).split("=", 1)[1]
    digits = "".join(ch for ch in stamp if ch.isdigit())
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}" if len(digits) >= 8 else stamp


def latest_partition(export_dir: str) -> str | None:
    parts = [p for pat in (PARTITION_PREFIX + "*", "dt=*") for p in glob.glob(os.path.join(export_dir, pat))
             if os.path.exists(os.path.join(p, "_SUCCESS"))]
    parts.sort(key=lambda p: (partition_date(p), os.path.basename(p)))
    return parts[-1] if parts else None


def partition_id(partition: str) -> str:
    """Identifies one export's contents: folder name, part file names and
    sizes. A re-exported partition (new generator, new catalog, same date -
    even with the same deterministic file names) gets a different id, so the
    backend reloads it instead of trusting the previous load."""
    parts = sorted(glob.glob(os.path.join(partition, "part-*.json")))
    sig = [os.path.basename(partition)] + [f"{os.path.basename(p)}:{os.path.getsize(p)}" for p in parts]
    return hashlib.sha1("|".join(sig).encode()).hexdigest()[:12]


def read_rows(partition: str):
    for path in sorted(glob.glob(os.path.join(partition, "part-*.json"))):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)


async def mark_live(guest_id: str):
    """Called after an action - remembers which guests have state newer than the export."""
    doc = await store.get("lookups", "live_guests") or {"guests": []}
    if guest_id not in doc["guests"]:
        doc["guests"].append(guest_id)
        await store.upsert("lookups", "live_guests", doc)


async def load(export_dir: str | None = None, force=False, kb=True) -> dict:
    export_dir = os.path.abspath(export_dir or config.RTCDP_EXPORT_DIR)
    part = latest_partition(export_dir)
    if not part:
        log.warning("No complete Real-Time CDP export (exportTime=*/_SUCCESS) under %s", export_dir)
        STATUS.update(state="no_export", export_dir=export_dir)
        return STATUS
    export_date = partition_date(part)
    state = await store.get("lookups", "load_state") or {}
    pid = partition_id(part)
    if (state.get("export_date") == export_date and state.get("partition_id") == pid and not force
            and state.get("driver") == store.driver and store.driver == "couchbase"):
        STATE["export_date"] = export_date
        STATUS.update(state="loaded", **state)
        log.info("Export %s already loaded", export_date)
        pb = await store.get("lookups", "kbdoc::playbook") or {}
        if kb and config.KB_ENABLED and aom.admin_enabled and pb.get("export_date") != export_date:
            # Loaded before AOM was configured (first run) - publish the KB now.
            _TASKS.append(asyncio.create_task(publish_kb(export_date, await _kb_window())))
        elif kb and aom.admin_enabled and pb.get("document_id"):
            # KB is current; make sure the RAG application points at it.
            _TASKS.append(asyncio.create_task(rag_app.sync(pb["document_id"])))
        return STATUS

    t0 = time.time()
    STATE["export_date"] = export_date
    STATUS.update(state="loading", export_date=export_date, partition=part, started_at=now_iso())
    live = set((await store.get("lookups", "live_guests") or {}).get("guests", []))
    today = dt.date.fromisoformat(config.DEMO_TODAY or export_date)
    bookings: dict[str, dict] = {}
    batch: dict[str, dict] = {}
    rows = skipped = carried = 0
    planning: list[tuple[int, str]] = []
    nbytes = sum(os.path.getsize(p) for p in glob.glob(os.path.join(part, "part-*.json")))

    for row in read_rows(part):
        gid = row["guest_id"]
        dts = (dt.date.fromisoformat(row["reservation"]["embark_date"]) - today).days
        if store.driver == "memory" and dts > config.MEMORY_WINDOW_DAYS and gid not in PERSONAS:
            skipped += 1
            continue
        doc = {**row, "type": "profile", "rev": 0, "channels": [guest_channel(gid)], "loaded_at": now_iso()}
        if gid in live:
            prev = await store.get("profiles", profile_id(gid))
            if prev and prev["reservation"]["booking_id"] == row["reservation"]["booking_id"]:
                for f in LIVE_FIELDS_RES:
                    if f in prev["reservation"]:
                        doc["reservation"][f] = prev["reservation"][f]
                doc["purchased_for_sailing"] = prev.get("purchased_for_sailing", doc["purchased_for_sailing"])
                doc["rev"] = int(prev.get("rev", 0)) + 1
                carried += 1
        batch[profile_id(gid)] = doc
        b = bookings.setdefault(row["reservation"]["booking_id"], {"type": "booking_index", "guests": [], "last_names": []})
        b["guests"].append(gid)
        ln = row["last_name"].lower()
        if ln not in b["last_names"]:
            b["last_names"].append(ln)
        if dts <= 45:
            planning.append((dts, gid))
        rows += 1
        if len(batch) >= 1000:
            await store.upsert_many("profiles", batch)
            batch = {}
            STATUS["rows"] = rows
    await store.upsert_many("profiles", batch)
    await store.upsert_many("lookups", {f"booking::{k}": v for k, v in bookings.items()})

    cat = C.public_catalog()
    cat.update({"type": "catalog", "faq": [{"q": f["q"], "a": f["a"], "keywords": f["keywords"]} for f in knowledge.FAQ],
                "export_date": export_date, "channels": [CATALOG_CHANNEL], "updated_at": now_iso()})
    await store.upsert("catalog", CATALOG_ID, cat)

    for _, gid in sorted(planning):
        await personalization.refresh_offers(gid)

    summary = {"export_date": export_date, "partition": part, "partition_id": pid, "rows": rows, "bookings": len(bookings),
               "skipped_outside_window": skipped, "carried_live_state": carried, "bytes": nbytes,
               "offers_ranked": len(planning), "load_seconds": round(time.time() - t0, 1),
               "driver": store.driver, "loaded_at": now_iso()}
    await store.upsert("lookups", "load_state", summary)
    STATUS.update(state="loaded", **summary)
    log.info("Loaded Real-Time CDP export %s: %s rows (%s bookings) in %.1fs", export_date, rows, len(bookings), time.time() - t0)

    if kb and config.KB_ENABLED and aom.admin_enabled:
        window = PERSONAS + [g for d, g in sorted(planning) if 0 <= d <= config.KB_WINDOW_DAYS and g not in PERSONAS]
        _TASKS.append(asyncio.create_task(publish_kb(export_date, window[: max(config.KB_PROFILE_LIMIT, len(PERSONAS))])))
    elif kb and config.KB_ENABLED:
        STATUS["kb"] = {"state": "skipped", "reason": "AOM_URL / AOM_ADMIN_PASSWORD not set"}
    return STATUS


async def _replace_kb_doc(key: str, title: str, content: str, metadata: dict, source: str = "adobe-rtcdp-export"):
    prev = await store.get("lookups", f"kbdoc::{key}")
    res = await aom.kb_ingest(title, content, metadata, source=source)
    new_id = res["document"]["document_id"]
    await store.upsert("lookups", f"kbdoc::{key}", {"type": "kb_index", "document_id": new_id, "title": title,
                                                    "export_date": metadata.get("export_date"), "at": now_iso()})
    if prev and prev.get("document_id") and prev["document_id"] != new_id:
        await aom.kb_delete(prev["document_id"])
    return new_id


async def publish_kb(export_date: str, guest_ids: list[str]):
    t0 = time.time()
    STATUS["kb"] = {"state": "publishing", "total": len(guest_ids) + 1, "done": 0, "errors": 0}
    try:
        entries, aem_mode = await adobe.playbook_entries(export_date)
        playbook_id = await _replace_kb_doc("playbook", f"Guest Services Playbook {export_date}",
                                            knowledge.playbook_markdown(export_date, entries),
                                            {"type": "playbook", "export_date": export_date, "pii": False,
                                             "source": "aem-content-fragments", "aem_mode": aem_mode},
                                            source="aem-content-fragments")
        STATUS["kb"]["aem_mode"] = aem_mode
        STATUS["kb"]["done"] += 1
        # Re-point the AOM RAG application at today's playbook document.
        await rag_app.sync(playbook_id)
    except AOMError as exc:
        log.error("KB playbook publish failed: %s", exc)
        STATUS["kb"].update(state="error", error=str(exc)[:300])
        return
    sem = asyncio.Semaphore(4)

    async def one(gid):
        async with sem:
            p = await store.get("profiles", profile_id(gid))
            if not p:
                return
            try:
                await _replace_kb_doc(gid, f"Guest profile {gid} {export_date}", knowledge.guest_profile_markdown(p),
                                      {"type": "guest_profile", "guest_id": gid, "export_date": export_date,
                                       "booking_id": p["reservation"]["booking_id"], "pii": True,
                                       "source": "adobe-rtcdp-export"})
                STATUS["kb"]["done"] += 1
            except AOMError as exc:
                STATUS["kb"]["errors"] += 1
                log.warning("KB publish for %s failed: %s", gid, exc)

    await asyncio.gather(*(one(g) for g in guest_ids))
    STATUS["kb"].update(state="published", seconds=round(time.time() - t0, 1), export_date=export_date)
    log.info("Published %d KB documents to AOM in %.1fs", STATUS["kb"]["done"], time.time() - t0)


async def poll_forever():
    while True:
        await asyncio.sleep(config.RTCDP_POLL_SECONDS)
        try:
            part = latest_partition(os.path.abspath(config.RTCDP_EXPORT_DIR))
            if part and partition_date(part) != STATE.get("export_date"):
                log.info("New Real-Time CDP export detected: %s", part)
                await load()
        except Exception as exc:  # noqa: BLE001
            log.warning("export poll failed: %s", exc)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--export-dir", "--dump-dir", dest="export_dir")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-kb", action="store_true")
    args = ap.parse_args()

    async def run():
        await store.connect()
        await load(args.export_dir, force=args.force, kb=False)
        if not args.no_kb and config.KB_ENABLED and aom.admin_enabled:
            state = await store.get("lookups", "load_state")
            await publish_kb(state["export_date"], await _kb_window())
        print(json.dumps({k: v for k, v in STATUS.items()}, indent=2, default=str))

    asyncio.run(run())


async def _kb_window() -> list[str]:
    """KB targets when run from the CLI (Couchbase mode): personas + guests in the window."""
    from .docs import days_to_sail
    out = list(PERSONAS)
    if store.driver == "memory":
        for key in list(store.data["profiles"]):
            p = store.data["profiles"][key]
            if p["guest_id"] not in out and 0 <= days_to_sail(p) <= config.KB_WINDOW_DAYS:
                out.append(p["guest_id"])
    else:
        rows = await store._query(
            f"SELECT RAW p.guest_id FROM {store._ks('profiles')} p WHERE p.reservation.embark_date <= $d "
            f"AND p.reservation.embark_date >= $t ORDER BY p.reservation.embark_date LIMIT $n",
            d=(dt.date.fromisoformat(STATE['export_date']) + dt.timedelta(days=config.KB_WINDOW_DAYS)).isoformat(),
            t=STATE["export_date"], n=config.KB_PROFILE_LIMIT)
        out += [g for g in rows if g not in out]
    return out[: max(config.KB_PROFILE_LIMIT, len(PERSONAS))]


if __name__ == "__main__":
    main()
