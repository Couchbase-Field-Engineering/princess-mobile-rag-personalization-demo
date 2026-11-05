"""Processes offline-first action requests.

The phone never calls a booking API directly. A tap writes a `requests`
document into Couchbase Lite (`status: "pending"`); the replicator pushes it
through Sync Gateway whenever the ship has connectivity, and this worker
picks it up from Couchbase, runs it through AOM (tool_gateway), and writes
the outcome back onto the same document. Sync Gateway replicates the update
to the phone, where a live query flips the card from "Waiting to sync" to
"Confirmed". Goodwill upgrades sit in `awaiting_approval` until a person
decides in AOM's Approvals page; this worker polls and re-invokes with the
approval id.
"""
from __future__ import annotations

import asyncio
import logging

from . import config, metrics, tool_gateway, upgrade_agent
from .actions import TOOLS
from .docs import guest_channel, now_iso
from .store import store

log = logging.getLogger("pcl.worker")

# Tools a guest's phone may request. Read-only tools are answered by the
# concierge; nothing here lets a phone name another guest.
REQUESTABLE = set(TOOLS) - {"get_guest_context", "get_upgrade_offers", "search_shore_excursions"}


async def process(key: str, doc: dict) -> dict:
    first = doc.get("status") != "awaiting_approval"
    guest_id = doc.get("guest_id")
    tool = doc.get("tool")
    if doc.get("status") == "awaiting_approval":
        status = await tool_gateway.approval_status(doc.get("approval_id", ""))
        if status in (None, "pending"):
            return doc
        if status != "approved":
            doc.update(status="failed", summary=f"Guest Services did not approve this request ({status}).",
                       completed_at=now_iso())
            await store.upsert("requests", key, doc)
            return doc
        result = await _run(doc, {**doc.get("args", {}), "guest_id": guest_id}, approval_id=doc["approval_id"])
    else:
        if tool not in REQUESTABLE:
            doc.update(status="failed", summary=f"'{tool}' can't be requested from the app", completed_at=now_iso())
            await store.upsert("requests", key, doc)
            return doc
        doc.update(status="processing", processing_at=now_iso())
        await store.upsert("requests", key, doc)
        # guest_id comes from the document, which Sync Gateway only accepted
        # from that signed-in guest (requireUser in the sync function).
        args = {k: v for k, v in (doc.get("args") or {}).items() if k != "guest_id"}
        result = await _run(doc, {**args, "guest_id": guest_id})

    status = result.get("status", "failed")
    if result.get("ok") and status in ("ok", "accepted"):
        status = "confirmed" if status == "ok" else status
    if not result.get("ok"):
        status = "failed"
    doc.update({
        "status": status, "summary": result.get("summary"), "charge_usd": result.get("charge_usd"),
        "item": result.get("item"), "governed": result.get("governed", False), "trace_id": result.get("trace_id"),
        "approval_id": result.get("approval_id", doc.get("approval_id")),
        "agent": result.get("agent", "princess-guest-concierge"),
        "memories_recalled": result.get("memories_recalled", 0), "remembered": result.get("remembered", False),
        "completed_at": None if status == "awaiting_approval" else now_iso(),
        "channels": [guest_channel(guest_id)],
    })
    await store.upsert("requests", key, doc)
    metrics.request(doc, first)
    log.info("request %s %s -> %s", key, tool, status)
    return doc


async def _run(doc: dict, args: dict, approval_id: str | None = None) -> dict:
    """Confirm on the upgrade screen creates one of the upgrade tools' requests:
    those run as the Stateroom Upgrade Agent (with Agent Memory). Everything
    else runs as the concierge."""
    if doc.get("tool") in upgrade_agent.TRIGGER_TOOLS:
        return await upgrade_agent.run(doc, args, approval_id=approval_id)
    return await tool_gateway.invoke(doc.get("tool"), args, approval_id=approval_id)


async def run_once() -> int:
    rows = await store.pending_requests()
    for key, doc in rows:
        try:
            await process(key, doc)
        except Exception as exc:  # noqa: BLE001
            log.exception("request %s failed", key)
            doc.update(status="failed", summary=f"Something went wrong: {exc}", completed_at=now_iso())
            await store.upsert("requests", key, doc)
    return len(rows)


async def loop():
    while True:
        try:
            await run_once()
        except Exception as exc:  # noqa: BLE001
            log.warning("worker tick failed: %s", exc)
        await asyncio.sleep(config.REQUEST_POLL_SECONDS)
