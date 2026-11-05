"""Princess Stateroom Upgrade Agent - the second AOM agent identity in the demo.

It is triggered by **Confirm** on the upgrade screen: the phone writes a
`requests` document (`purchase_cabin_upgrade`, `place_upgrade_bid` or
`apply_goodwill_upgrade`), and the worker hands any of those three tools to
this agent instead of the concierge. One upgrade = one AOM run, attributed
to the *Princess Stateroom Upgrade Agent* on AOM's Agents, Traces and Audit
pages, scoped to the five upgrade tools only.

What makes it an agent rather than a tool call is **AOM Agent Memory**:

1. Before applying the upgrade it recalls what AOM already remembers about
   this guest's staterooms (`POST /v1/memory/search`): earlier upgrades,
   bids, and anything the guest told the concierge about rooms.
2. After the upgrade is applied it writes an episodic memory
   (`POST /v1/memory`) - from which category to which, stateroom, deck,
   sailing, what was paid or bid, and the occasion - plus a semantic
   preference memory when the booking shows one (location preference, bed).

The concierge recalls the same memories on its next turn, so "can we upgrade
again next time?" is answered with what actually happened.
"""
from __future__ import annotations

import logging

from . import catalog as C, config, tool_gateway
from .aom_client import AOMError, upgrade_aom
from .store import store

log = logging.getLogger("pcl.upgrade_agent")

AGENT_ID = "princess-upgrade-agent"
AGENT_NAME = "Princess Stateroom Upgrade Agent"
TOOLS = ["get_guest_context", "get_upgrade_offers", "place_upgrade_bid", "purchase_cabin_upgrade",
         "apply_goodwill_upgrade"]
# Tools the worker routes to this agent (the request documents a Confirm creates).
TRIGGER_TOOLS = {"place_upgrade_bid", "purchase_cabin_upgrade", "apply_goodwill_upgrade"}
DESCRIPTION = ("Princess Cruises stateroom upgrade agent. Triggered when a guest confirms an upgrade in the mobile "
               "app: recalls the guest's stateroom history and preferences from Agent Memory, applies the upgrade, "
               "bid or complimentary move as a governed tool call, and remembers the outcome for the concierge.")


def enabled() -> bool:
    return upgrade_aom.enabled


async def recall(guest_id: str) -> list[str]:
    if not enabled():
        return []
    try:
        res = await upgrade_aom.memory_search(guest_id, "stateroom upgrade bid suite cabin preference", top_k=4)
        return [e.get("content", "") for e in res.get("entries", []) if e.get("content")]
    except AOMError as exc:
        log.info("memory search skipped: %s", exc)
        return []


def _episode(tool: str, profile: dict, before: dict, result: dict) -> str:
    r = profile.get("reservation") or {}
    item = result.get("item") or {}
    room = item.get("stateroom") or {}
    occasion = (profile.get("preferences") or {}).get("celebration")
    sailing = f"{r.get('ship_name')} ({r.get('itinerary_name')}, embarking {r.get('embark_date')})"
    frm = f"{before.get('category_name')} {before.get('stateroom_number')} on deck {before.get('deck')}"
    if tool == "place_upgrade_bid":
        bid = item.get("bid_ppn")
        what = (f"placed a Princess Upgrade bid of ${bid:,.0f}/person/night" if bid else "placed a Princess Upgrade bid")
        if result.get("status") == "accepted":
            what += f" that was accepted: now in {room.get('category_name')} {room.get('stateroom_number')}"
        else:
            cat = C.CATEGORY_BY_CODE.get(item.get("to_category") or "", {}).get("name", "a higher category")
            what += f" for {C.a_or_an(cat) if cat != 'a higher category' else cat} (pending the revenue team)"
    elif tool == "apply_goodwill_upgrade":
        what = (f"was moved to {room.get('category_name')} {room.get('stateroom_number')} as a complimentary goodwill "
                f"upgrade approved by Guest Services")
    else:
        charge = result.get("charge_usd")
        what = (f"bought an instant upgrade to {room.get('category_name')} {room.get('stateroom_number')} on deck "
                f"{room.get('deck')}" + (f" for ${charge:,.0f}" if charge else ""))
    txt = f"Stateroom upgrade: {what}, from {frm}, on {sailing}"
    if occasion:
        txt += f", celebrating their {occasion}"
    return txt + "."


def _preference(profile: dict) -> str | None:
    prefs = profile.get("preferences") or {}
    bits = []
    if prefs.get("stateroom_location_pref"):
        bits.append(f"prefers a {prefs['stateroom_location_pref']} stateroom")
    if prefs.get("bed_configuration"):
        bits.append(f"bed: {prefs['bed_configuration']}")
    if prefs.get("pillow") and prefs["pillow"] != "standard":
        bits.append(f"{prefs['pillow']} pillow")
    return ("Stateroom preferences: " + ", ".join(bits) + ".") if bits else None


async def run(doc: dict, args: dict, approval_id: str | None = None) -> dict:
    """Apply an upgrade request as the Stateroom Upgrade Agent. Returns the
    tool result plus `agent`, `memories_recalled` and `remembered`."""
    guest_id = doc.get("guest_id")
    tool = doc.get("tool")
    profile = await store.get("profiles", f"profile::{guest_id}") or {}
    before = dict((profile.get("reservation") or {}).get("stateroom") or {})

    memories = await recall(guest_id)
    result = await tool_gateway.invoke(tool, args, approval_id=approval_id, client=upgrade_aom if enabled() else None)
    result.update({"agent": AGENT_ID, "memories_recalled": len(memories), "remembered": False})

    if result.get("ok") and result.get("status") in ("ok", "confirmed", "accepted", "submitted") and enabled():
        try:
            after = await store.get("profiles", f"profile::{guest_id}") or profile
            await upgrade_aom.memory_add(
                guest_id, _episode(tool, after, before, result), session_id=doc.get("session_id"),
                memory_type="episodic",
                metadata={"agent": AGENT_ID, "tool": tool, "sailing_id": (after.get("reservation") or {}).get("sailing_id"),
                          "trace_id": result.get("trace_id"), "app": "pcl-mobile"})
            pref = _preference(after)
            if pref and not any("Stateroom preferences:" in m for m in memories):
                await upgrade_aom.memory_add(guest_id, pref, memory_type="semantic",
                                             metadata={"agent": AGENT_ID, "app": "pcl-mobile"})
            result["remembered"] = True
        except AOMError as exc:
            log.info("memory add skipped: %s", exc)
    if memories and result.get("summary"):
        last = next((m for m in memories if m.startswith("Stateroom upgrade:")), None)
        if last:
            result["summary"] += f" (The upgrade agent remembered: {last[len('Stateroom upgrade: '):].rstrip('.')}.)"
    return result
