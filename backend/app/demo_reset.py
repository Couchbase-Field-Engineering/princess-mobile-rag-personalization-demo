"""Reset the demo: put guests back to the state of today's Databricks export
and clear what they left behind, here and in AOM.

`POST /api/demo/reset` (the story page's **Reset demo** button, or
scripts/reset_demo.py). For each guest - by default the three personas plus
every guest who changed something since the dump loaded:

1. **Couchbase**: delete their `requests` (the upgrade/booking queue the phone
   shows), `concierge` chat, `context_cache` and `bookings` documents; reload
   their `profiles` document from the dump partition (stateroom, check-in,
   purchases, `rev` back to the export); release the sold staterooms of their
   sailing (`inventory`, rebuilt from the catalog on next use); re-rank their
   offers; drop them from `live_guests` so the next daily load doesn't carry
   the old state forward. Sync Gateway replicates the deletes and the fresh
   profile to the phone, so Couchbase Lite ends up in the same state.
2. **AOM Agent Memory**: delete every memory entry for the guest (what they
   told the concierge, and what the Stateroom Upgrade Agent remembered).
3. **AOM caches** (optional, default on): purge the concierge's LLM Cache
   namespaces and its Context Cache namespace, so the next demo starts with a
   visible `miss` again. Everything else in AOM (traces, audit log, approvals
   history) is left alone - that is the record.
4. The backend's in-process counters and the last fleet-workload report.

Nothing here touches the dump, the Knowledge Base or the RAG application.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

from . import concierge, config, loader, metrics, personalization, workload
from .aom_client import AOMError, aom
from .docs import (STATE, bookings_id, chat_id, guest_channel, inventory_id, now_iso, offers_id,
                   profile_id)
from .store import store

log = logging.getLogger("pcl.reset")
LAST: dict = {"state": "never"}


async def default_guests() -> list[str]:
    live = (await store.get("lookups", "live_guests") or {}).get("guests", [])
    return list(dict.fromkeys(loader.PERSONAS + list(live)))


def _dump_rows(guest_ids: set[str]) -> dict[str, dict]:
    """The export rows of these guests (personas are first in part-00000)."""
    part = loader.latest_partition(os.path.abspath(config.DUMP_DIR))
    found: dict[str, dict] = {}
    if not part:
        return found
    for row in loader.read_rows(part):
        if row["guest_id"] in guest_ids:
            found[row["guest_id"]] = row
            if len(found) == len(guest_ids):
                break
    return found


async def _reset_guest(gid: str, row: dict | None, aom_memory: bool) -> dict:
    out = {"guest_id": gid, "requests": 0, "docs": [], "profile": "kept", "memories": 0, "inventory": None}
    for d in await store.requests_for_guest(gid):
        await store.remove("requests", d["_id"])
        out["requests"] += 1
    for col, key in (("concierge", chat_id(gid)), ("bookings", bookings_id(gid)), ("offers", offers_id(gid))):
        if await store.get(col, key):
            await store.remove(col, key)
            out["docs"].append(col)
    await concierge.invalidate_context(gid)
    prev = await store.get("profiles", profile_id(gid))
    if row:
        doc = {**row, "type": "profile", "rev": 0, "channels": [guest_channel(gid)], "loaded_at": now_iso()}
        await store.upsert("profiles", profile_id(gid), doc)
        out["profile"] = "reloaded"
        sailing = (prev or row)["reservation"].get("sailing_id")
        if sailing and await store.get("inventory", inventory_id(sailing)):
            await store.remove("inventory", inventory_id(sailing))   # rebuilt from the catalog on next use
            out["inventory"] = sailing
    elif prev:
        out["profile"] = "not in dump"
    if await store.get("profiles", profile_id(gid)):
        await personalization.refresh_offers(gid)
    if aom_memory and aom.enabled:
        try:
            for m in await aom.memory_list(gid):
                if m.get("memory_id") and await aom.memory_delete(m["memory_id"]):
                    out["memories"] += 1
        except AOMError as exc:
            out["memory_error"] = str(exc)[:200]
    return out


async def _purge_aom_caches() -> dict:
    """Purge every AOM cache namespace that belongs to the concierge: the
    namespaces it calls directly (`rag:<app>:playbook|personal|guest-context`)
    and the ones AOM's RAG application made for it (`rag:<app>` and
    `rag:<app>:<fingerprint>`). AOM purges by exact namespace, so list first."""
    prefix = f"rag:{config.RAG_APP_ID}"
    out: dict = {}
    try:
        llm_ns = {config.LLM_NAMESPACE_PLAYBOOK, config.LLM_NAMESPACE_PERSONAL}
        ctx_ns = {config.CONTEXT_NAMESPACE}
        for _ in range(4):  # the listing is capped at 500 entries; look again until nothing is left
            more_llm = await aom.llm_cache_namespaces(prefix) - llm_ns
            more_ctx = await aom.context_cache_namespaces(prefix) - ctx_ns
            llm_ns |= more_llm
            ctx_ns |= more_ctx
            for ns in sorted(llm_ns):
                out.setdefault(ns, {})["llm_purged"] = out.get(ns, {}).get("llm_purged", 0) + await aom.purge_llm_cache(ns)
            for ns in sorted(ctx_ns):
                out.setdefault(ns, {})["context_purged"] = out.get(ns, {}).get("context_purged", 0) + await aom.purge_context_cache(ns)
            if not more_llm and not more_ctx:
                break
    except AOMError as exc:
        out["error"] = str(exc)[:200]
    return out


async def run(guests: list[str] | None = None, aom_memory: bool = True, aom_caches: bool = True,
              counters: bool = True) -> dict:
    t0 = time.time()
    gids = list(dict.fromkeys(guests)) if guests else await default_guests()
    rows = await asyncio.to_thread(_dump_rows, set(gids))
    results = [await _reset_guest(g, rows.get(g), aom_memory) for g in gids]
    live = await store.get("lookups", "live_guests")
    if live:
        live["guests"] = [g for g in live.get("guests", []) if g not in gids]
        await store.upsert("lookups", "live_guests", live)
    caches: dict = {}
    if aom_caches and aom.admin_enabled:
        caches = await _purge_aom_caches()
    elif aom_caches:
        caches = {"skipped": "AOM admin password not configured" if aom.enabled else "AOM not configured"}
    if counters:
        metrics.reset()
        if workload.RUN.get("state") != "running":
            workload.RUN.clear()
            workload.RUN["state"] = "idle"
    LAST.clear()
    LAST.update(state="done", at=now_iso(), seconds=round(time.time() - t0, 1), export_date=STATE.get("export_date"),
                guests=results, aom_memory=aom_memory, aom_caches=caches, counters=counters,
                summary={"guests": len(results), "requests_removed": sum(r["requests"] for r in results),
                         "profiles_reloaded": sum(r["profile"] == "reloaded" for r in results),
                         "memories_deleted": sum(r["memories"] for r in results)})
    log.info("Demo reset: %s", LAST["summary"])
    return dict(LAST)
