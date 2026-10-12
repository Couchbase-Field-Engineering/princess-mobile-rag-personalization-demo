"""`rccl-guest-services` - the MCP server registered with AOM.

Streamable HTTP at /rccl/mcp/. AOM ingests these tool definitions into its
vetted catalog (embeddings for discovery, RBAC per role, drift detection)
and is the only caller the demo expects: the app and concierge reach these
tools through `POST /v1/tools/invoke`, never directly.

Business errors (sold out, bad date) come back as `{"ok": false, ...}`
results rather than MCP errors, so AOM records a completed call and the
guest gets a useful message instead of a gateway failure.
"""
from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from . import actions

log = logging.getLogger("rccl.mcp")

mcp = FastMCP(
    "rccl-guest-services",
    instructions=("Royal Caribbean guest services for a guest's upcoming sailing: stateroom upgrades (RoyalUp bids, "
                  "instant and goodwill upgrades), shore excursions, specialty dining, packages, spa and online check-in."),
    stateless_http=True,
    # Called by AOM over the Docker host gateway, so the Host header is not
    # localhost; same reasoning as AOM's own bundled sample servers.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


async def _run(fn, **kw) -> dict:
    try:
        res = await fn(**kw)
    except actions.ToolError as exc:
        return {"ok": False, "status": "failed", "summary": str(exc)}
    return res if isinstance(res, dict) and "ok" in res else {"ok": True, "status": "ok", "data": res}


@mcp.tool()
async def get_guest_context(guest_id: str) -> dict:
    """Read a cruise guest's upcoming sailing, stateroom, party, loyalty tier, preferences and personalization segment."""
    return await _run(actions.get_guest_context, guest_id=guest_id)


@mcp.tool()
async def get_upgrade_offers(guest_id: str) -> dict:
    """List stateroom upgrade options for a guest's sailing: categories above theirs, unsold inventory, instant upgrade price and RoyalUp minimum bid."""
    return await _run(actions.get_upgrade_offers, guest_id=guest_id)


@mcp.tool()
async def place_royalup_bid(guest_id: str, category_code: str, bid_per_night_usd: float) -> dict:
    """Place a RoyalUp bid (per person per night, USD) to upgrade a guest's stateroom to a higher category (OV, BA, JS, GS, OS, RL). Charged only if accepted."""
    return await _run(actions.place_royalup_bid, guest_id=guest_id, category_code=category_code,
                      bid_per_night_usd=bid_per_night_usd)


@mcp.tool()
async def purchase_cabin_upgrade(guest_id: str, category_code: str) -> dict:
    """Instantly purchase a paid stateroom upgrade to a higher category for the whole stateroom party and reassign the stateroom."""
    return await _run(actions.purchase_cabin_upgrade, guest_id=guest_id, category_code=category_code)


@mcp.tool()
async def apply_goodwill_upgrade(guest_id: str, category_code: str, reason: str) -> dict:
    """Apply a complimentary (no-charge) goodwill stateroom upgrade as a guest-recovery gesture. Requires a reason; held for supervisor approval."""
    return await _run(actions.apply_goodwill_upgrade, guest_id=guest_id, category_code=category_code, reason=reason)


@mcp.tool()
async def search_shore_excursions(guest_id: str, port_code: str = "", interest: str = "") -> dict:
    """Find shore excursions at the ports on a guest's itinerary, ranked by the guest's interests (snorkeling, beach, history, thrill...)."""
    return await _run(actions.search_shore_excursions, guest_id=guest_id, port_code=port_code, interest=interest)


@mcp.tool()
async def book_shore_excursion(guest_id: str, excursion_id: str, participants: int = 0) -> dict:
    """Book a shore excursion for a guest and their party (participants defaults to the whole party)."""
    return await _run(actions.book_shore_excursion, guest_id=guest_id, excursion_id=excursion_id, participants=participants)


@mcp.tool()
async def reserve_specialty_dining(guest_id: str, restaurant_id: str, date: str, time: str, party_size: int = 0) -> dict:
    """Reserve a specialty restaurant table (e.g. CHOPS, GIOVANNI, IZUMI, CHEFSTABLE) on a night of the sailing. date is YYYY-MM-DD, time HH:MM."""
    return await _run(actions.reserve_specialty_dining, guest_id=guest_id, restaurant_id=restaurant_id, date=date,
                      time=time, party_size=party_size)


@mcp.tool()
async def purchase_package(guest_id: str, package_code: str) -> dict:
    """Purchase a cruise package for the sailing: DELUXE_BEV, REFRESH, VOOM (internet), THE_KEY or ULT_DINING."""
    return await _run(actions.purchase_package, guest_id=guest_id, package_code=package_code)


@mcp.tool()
async def book_spa_treatment(guest_id: str, treatment_id: str, date: str, time: str = "10:00") -> dict:
    """Book a Vitality Spa treatment (massage, facial, thermal suite) on a day of the sailing. Port days are discounted."""
    return await _run(actions.book_spa_treatment, guest_id=guest_id, treatment_id=treatment_id, date=date, time=time)


@mcp.tool()
async def complete_online_checkin(guest_id: str, arrival_slot: str) -> dict:
    """Complete online check-in for a guest's stateroom party and reserve a terminal arrival time to get the SetSail Pass."""
    return await _run(actions.complete_online_checkin, guest_id=guest_id, arrival_slot=arrival_slot)
