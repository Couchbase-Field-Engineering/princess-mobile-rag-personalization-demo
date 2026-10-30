"""Guest-service actions - the business logic behind every MCP tool.

These functions are what actually changes state (staterooms, inventory,
bookings, check-in). They are only ever reached through `tool_gateway`,
which routes them through the Couchbase Agent Operations Manager when it is
configured (RBAC, approvals, tracing, audit) and calls them in-process
otherwise. Every mutation bumps the guest's profile `rev`, which is what
invalidates that guest's context cache and re-ranks their offers.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import uuid

from . import catalog as C
from .docs import (bookings_id, days_to_sail, guest_channel, inventory_id, money, now_iso,
                   profile_id)
from .store import store


class ToolError(Exception):
    pass


def _h(*parts) -> int:
    return int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
async def load_profile(guest_id: str) -> dict:
    p = await store.get("profiles", profile_id(guest_id))
    if not p:
        raise ToolError(f"No guest profile for '{guest_id}'")
    return p


def party_ids(profile) -> list[str]:
    return [m["guest_id"] for m in profile["reservation"]["party"]]


def adults(profile) -> int:
    return sum(1 for m in profile["reservation"]["party"] if m["age_band"] not in ("0-2", "3-5", "6-11", "12-17")) or 1


async def save_profiles(updates: dict[str, dict]):
    for gid, p in updates.items():
        p["rev"] = int(p.get("rev", 0)) + 1
        p["updated_at"] = now_iso()
        await store.upsert("profiles", profile_id(gid), p)
        from .loader import mark_live  # late import: loader -> personalization -> actions
        await mark_live(gid)


async def record_booking(guest_ids: list[str], item: dict):
    for gid in guest_ids:
        doc = await store.get("bookings", bookings_id(gid)) or {
            "type": "bookings", "guest_id": gid, "items": [], "channels": [guest_channel(gid)]}
        doc["items"] = [i for i in doc["items"] if i.get("item_id") != item["item_id"]] + [item]
        doc["updated_at"] = now_iso()
        await store.upsert("bookings", bookings_id(gid), doc)


async def after_change(guest_ids: list[str]):
    # late imports: personalization/concierge import this module
    from . import concierge, personalization
    for gid in guest_ids:
        await personalization.refresh_offers(gid)
        await concierge.invalidate_context(gid)


async def get_inventory(sailing_id: str) -> tuple[dict, int]:
    doc, cas = await store.get_with_cas("inventory", inventory_id(sailing_id))
    if doc is None:
        await store.insert("inventory", inventory_id(sailing_id),
                           {"type": "inventory", "sailing_id": sailing_id, "available": C.initial_inventory(sailing_id),
                            "created_at": now_iso()})
        doc, cas = await store.get_with_cas("inventory", inventory_id(sailing_id))
    return doc, cas


async def take_inventory(sailing_id: str, code: str):
    for _ in range(10):
        doc, cas = await get_inventory(sailing_id)
        if doc["available"].get(code, 0) <= 0:
            raise ToolError(f"No {C.CATEGORY_BY_CODE[code]['name']} staterooms are left on this sailing")
        doc["available"][code] -= 1
        if await store.replace_cas("inventory", inventory_id(sailing_id), doc, cas):
            return doc["available"][code]
    raise ToolError("Inventory is busy - please try again")


def _new_stateroom(profile, code) -> dict:
    cat = C.CATEGORY_BY_CODE[code]
    lo, hi = cat["decks"]
    seed = _h(profile["reservation"]["booking_id"], code)
    deck = lo + seed % (hi - lo + 1)
    hoods = C.SHIPS[profile["reservation"]["ship_code"]]["neighborhoods"]
    return {"stateroom_number": f"{deck}{100 + seed % 600:03d}", "deck": deck, "category_code": code,
            "category_name": cat["name"], "neighborhood": hoods[seed % len(hoods)],
            "location": ["Forward", "Midship", "Aft"][seed % 3]}


def _item(kind: str, title: str, **kw) -> dict:
    return {"item_id": f"{kind}-{uuid.uuid4().hex[:10]}", "kind": kind, "title": title, "status": "confirmed",
            "booked_at": now_iso(), **kw}


def _sailing_dates(profile) -> list[str]:
    return [p["date"] for p in profile["reservation"]["ports"]]


async def _reassign(profile, to_code: str, how: str, charge: float, extra: dict) -> dict:
    res = profile["reservation"]
    old = dict(res["stateroom"])
    new = _new_stateroom(profile, to_code)
    party = party_ids(profile)
    updates = {}
    for gid in party:
        p = profile if gid == profile["guest_id"] else (await store.get("profiles", profile_id(gid)))
        if not p:
            continue
        p["reservation"]["stateroom"] = new
        p["reservation"].setdefault("upgrade_history", []).append(
            {"from": old, "to": new, "how": how, "charge_usd": charge, "at": now_iso(), **extra})
        updates[gid] = p
    await save_profiles(updates)
    item = _item("upgrade", f"Upgrade to {new['category_name']} · Stateroom {new['stateroom_number']}",
                 how=how, from_category=old["category_code"], to_category=to_code, stateroom=new,
                 charge_usd=charge, date=res["embark_date"], **extra)
    await record_booking(party, item)
    await after_change(party)
    return item


# --------------------------------------------------------------------------
# tools
# --------------------------------------------------------------------------
async def get_guest_context(guest_id: str) -> dict:
    p = await load_profile(guest_id)
    r = p["reservation"]
    return {
        "guest_id": guest_id, "name": f"{p['first_name']} {p['last_name']}",
        "loyalty": p["loyalty"], "ship": r["ship_name"], "itinerary": r["itinerary_name"],
        "embark_date": r["embark_date"], "days_to_sail": days_to_sail(p), "stateroom": r["stateroom"],
        "party": r["party"], "checkin_status": r["checkin_status"], "preferences": p["preferences"],
        "segment": p["ml_scores"].get("segment"), "next_best_action": p["ml_scores"].get("next_best_action"),
        "purchased": p.get("purchased_for_sailing", {}),
    }


async def get_upgrade_offers(guest_id: str) -> dict:
    p = await load_profile(guest_id)
    r = p["reservation"]
    cur = r["stateroom"]["category_code"]
    inv, _ = await get_inventory(r["sailing_id"])
    rank = C.CATEGORY_BY_CODE[cur]["rank"]
    offers = []
    for cat in C.CABIN_CATEGORIES:
        if cat["rank"] <= rank or cat["rank"] > rank + 3:
            continue
        left = inv["available"].get(cat["code"], 0)
        ppn = C.upgrade_price_ppn(cur, cat["code"])
        min_bid = C.upgrade_bid_min(cur, cat["code"])
        offers.append({
            "category_code": cat["code"], "category_name": cat["name"], "available": left,
            "instant_price_ppn": ppn, "instant_total_usd": ppn * r["nights"] * r["party_size"],
            "upgrade_bid_min_ppn": min_bid, "perks": C.CATEGORY_PERKS.get(cat["code"], []),
            "recommended": cat["code"] == p["ml_scores"].get("recommended_upgrade_category"),
            "recommended_bid_ppn": p["ml_scores"].get("recommended_bid_per_night_usd")
            if cat["code"] == p["ml_scores"].get("recommended_upgrade_category") else None,
        })
    return {"guest_id": guest_id, "sailing_id": r["sailing_id"], "current": r["stateroom"], "nights": r["nights"],
            "party_size": r["party_size"], "days_to_sail": days_to_sail(p), "offers": offers}


def _validate_upgrade(p, to_code):
    if to_code not in C.CATEGORY_BY_CODE:
        raise ToolError(f"Unknown stateroom category '{to_code}'")
    cur = p["reservation"]["stateroom"]["category_code"]
    if C.CATEGORY_BY_CODE[to_code]["rank"] <= C.CATEGORY_BY_CODE[cur]["rank"]:
        raise ToolError(f"{C.CATEGORY_BY_CODE[to_code]['name']} is not an upgrade from {C.CATEGORY_BY_CODE[cur]['name']}")
    if days_to_sail(p) < 0:
        raise ToolError("This sailing has already departed")
    return cur


async def place_upgrade_bid(guest_id: str, category_code: str, bid_per_night_usd: float) -> dict:
    p = await load_profile(guest_id)
    cur = _validate_upgrade(p, category_code)
    r = p["reservation"]
    min_bid = C.upgrade_bid_min(cur, category_code)
    list_ppn = C.upgrade_price_ppn(cur, category_code)
    bid = float(bid_per_night_usd)
    if bid < min_bid:
        raise ToolError(f"Minimum Princess Upgrade bid for {C.CATEGORY_BY_CODE[category_code]['name']} is {money(min_bid)} per person per night")
    if bid > list_ppn:
        raise ToolError(f"That bid is above the instant upgrade price ({money(list_ppn)}) - buy it instantly instead")
    # The revenue team's clearing price for this sailing/category (deterministic per sailing).
    factor = 0.25 + (_h(r["sailing_id"], category_code, "clear") % 35) / 100
    clearing = min_bid + (list_ppn - min_bid) * factor
    total = round(bid * r["nights"] * r["party_size"], 2)
    if bid >= clearing:
        await take_inventory(r["sailing_id"], category_code)
        item = await _reassign(p, category_code, "upgrade_bid", total, {"bid_ppn": bid})
        return {"ok": True, "status": "accepted", "charge_usd": total, "item": item,
                "summary": f"Princess Upgrade bid accepted! You're now in {item['stateroom']['category_name']} "
                           f"stateroom {item['stateroom']['stateroom_number']}. {money(total)} charged to your card on file."}
    item = _item("upgrade_bid", f"Princess Upgrade bid · {C.CATEGORY_BY_CODE[category_code]['name']}",
                 status="submitted", to_category=category_code, bid_ppn=bid, potential_charge_usd=total,
                 date=r["embark_date"])
    await record_booking([guest_id], item)
    await after_change([guest_id])
    return {"ok": True, "status": "submitted", "charge_usd": 0, "item": item,
            "summary": f"Bid of {money(bid)}/person/night submitted for {C.CATEGORY_BY_CODE[category_code]['name']}. "
                       "You'll only be charged if it's accepted - we'll notify you before sailing."}


async def purchase_cabin_upgrade(guest_id: str, category_code: str) -> dict:
    p = await load_profile(guest_id)
    cur = _validate_upgrade(p, category_code)
    r = p["reservation"]
    total = C.upgrade_price_ppn(cur, category_code) * r["nights"] * r["party_size"]
    await take_inventory(r["sailing_id"], category_code)
    item = await _reassign(p, category_code, "instant", total, {})
    return {"ok": True, "status": "confirmed", "charge_usd": total, "item": item,
            "summary": f"Upgraded to {item['stateroom']['category_name']} - stateroom {item['stateroom']['stateroom_number']} "
                       f"on deck {item['stateroom']['deck']} ({item['stateroom']['neighborhood']}). {money(total)} charged."}


async def apply_goodwill_upgrade(guest_id: str, category_code: str, reason: str) -> dict:
    """Complimentary upgrade - a guest-services recovery gesture. Held for a
    human decision in AOM's approval tier before it can run."""
    if not reason or len(reason.strip()) < 5:
        raise ToolError("A goodwill upgrade needs a reason for the audit trail")
    p = await load_profile(guest_id)
    _validate_upgrade(p, category_code)
    await take_inventory(p["reservation"]["sailing_id"], category_code)
    item = await _reassign(p, category_code, "goodwill", 0.0, {"reason": reason.strip()[:300]})
    return {"ok": True, "status": "confirmed", "charge_usd": 0, "item": item,
            "summary": f"Complimentary upgrade to {item['stateroom']['category_name']} applied - stateroom "
                       f"{item['stateroom']['stateroom_number']}. Reason recorded: {reason.strip()[:120]}"}


async def search_shore_excursions(guest_id: str, port_code: str = "", interest: str = "") -> dict:
    p = await load_profile(guest_id)
    r = p["reservation"]
    port_days = {d["port_code"]: d for d in r["ports"] if d["type"] == "port"}
    likes = set(p["preferences"]["interests"])
    if interest:
        likes.add(interest.lower())
    owned = set(p.get("purchased_for_sailing", {}).get("excursions", []))
    out = []
    for e in C.EXCURSIONS:
        if e["port"] not in port_days or (port_code and e["port"] != port_code.upper()):
            continue
        match = sorted(likes & set(e["tags"]))
        kid_ok = not ("adults" in e["tags"] and p["preferences"].get("travels_with_kids"))
        out.append({**e, "port_name": C.PORTS[e["port"]], "date": port_days[e["port"]]["date"],
                    "matched_interests": match, "family_friendly": kid_ok, "already_booked": e["id"] in owned,
                    "score": round(len(match) * 0.3 + (0.15 if kid_ok else -0.3), 2)})
    out.sort(key=lambda e: (-e["score"], e["price"]))
    return {"guest_id": guest_id, "excursions": out[:12]}


async def book_shore_excursion(guest_id: str, excursion_id: str, participants: int = 0) -> dict:
    p = await load_profile(guest_id)
    r = p["reservation"]
    e = C.EXCURSION_BY_ID.get(excursion_id)
    if not e:
        raise ToolError(f"Unknown excursion '{excursion_id}'")
    day = next((d for d in r["ports"] if d["port_code"] == e["port"] and d["type"] == "port"), None)
    if not day:
        raise ToolError(f"{e['name']} is in {C.PORTS[e['port']]}, which isn't on this itinerary")
    n = int(participants or r["party_size"])
    if n < 1 or n > r["party_size"]:
        raise ToolError(f"Participants must be between 1 and {r['party_size']}")
    total = e["price"] * n
    party = party_ids(p)[:n]
    updates = {}
    for gid in party:
        gp = p if gid == guest_id else await store.get("profiles", profile_id(gid))
        if gp:
            gp.setdefault("purchased_for_sailing", {}).setdefault("excursions", []).append(excursion_id)
            updates[gid] = gp
    await save_profiles(updates)
    item = _item("excursion", e["name"], excursion_id=excursion_id, port=C.PORTS[e["port"]], date=day["date"],
                 time=day.get("arrive") or "08:00", participants=n, charge_usd=total)
    await record_booking(party, item)
    await after_change(party)
    return {"ok": True, "status": "confirmed", "charge_usd": total, "item": item,
            "summary": f"Booked {e['name']} in {C.PORTS[e['port']]} on {day['date']} for {n} "
                       f"guest{'s' if n > 1 else ''} - {money(total)}."}


async def reserve_specialty_dining(guest_id: str, restaurant_id: str, date: str, time: str, party_size: int = 0) -> dict:
    p = await load_profile(guest_id)
    r = p["reservation"]
    d = C.DINING_BY_ID.get(restaurant_id)
    if not d:
        raise ToolError(f"Unknown restaurant '{restaurant_id}'")
    if not C.ship_has_dining(r["ship_code"], restaurant_id):
        raise ToolError(f"{d['name']} isn't on {r['ship_name']}")
    if date not in _sailing_dates(p)[:-1]:
        raise ToolError(f"Pick a night between {r['embark_date']} and the night before {r['debark_date']}")
    if time not in C.DINING_TIMES:
        raise ToolError(f"Choose one of these times: {', '.join(C.DINING_TIMES)}")
    n = int(party_size or r["party_size"])
    if C.dining_full(r["sailing_id"], restaurant_id, date, time):
        alts = [t for t in C.DINING_TIMES if not C.dining_full(r["sailing_id"], restaurant_id, date, t)][:3]
        raise ToolError(f"{d['name']} is fully booked at {time} on {date}. Open times that night: {', '.join(alts)}")
    total = d["price_pp"] * n
    note = " We've let the restaurant know you're celebrating your " + p["preferences"]["celebration"] + "." \
        if p["preferences"].get("celebration") else ""
    diet = p["preferences"].get("dietary") or []
    item = _item("dining", f"{d['name']} · {n} guests", restaurant_id=restaurant_id, date=date, time=time,
                 party_size=n, charge_usd=total, dietary=diet, celebration=p["preferences"].get("celebration"))
    await record_booking([guest_id], item)
    p.setdefault("purchased_for_sailing", {}).setdefault("dining", []).append(restaurant_id)
    await save_profiles({guest_id: p})
    await after_change([guest_id])
    return {"ok": True, "status": "confirmed", "charge_usd": total, "item": item,
            "summary": f"Table for {n} at {d['name']} on {date} at {time} - {money(total)}.{note}"
                       + (f" Dietary notes shared: {', '.join(diet)}." if diet else "")}


async def purchase_package(guest_id: str, package_code: str) -> dict:
    p = await load_profile(guest_id)
    r = p["reservation"]
    pkg = C.PACKAGE_BY_CODE.get(package_code)
    if not pkg:
        raise ToolError(f"Unknown package '{package_code}'")
    if package_code in p.get("purchased_for_sailing", {}).get("packages", []):
        raise ToolError(f"You already have the {pkg['name']}")
    if package_code == "PLUS" and p["age_band"] in ("0-2", "3-5", "6-11", "12-17"):
        raise ToolError("The Princess Plus is for guests 21 and over")
    qty = 1 if pkg["per"].startswith("device") else (adults(p) if package_code in ("PLUS", "ZERO_ALC") else 1)
    total = pkg["price_per_day"] * r["nights"] * qty
    p.setdefault("purchased_for_sailing", {}).setdefault("packages", []).append(package_code)
    await save_profiles({guest_id: p})
    item = _item("package", pkg["name"], package_code=package_code, quantity=qty, charge_usd=total, date=r["embark_date"])
    await record_booking([guest_id], item)
    await after_change([guest_id])
    rule = " (beverage packages are purchased for every adult in the stateroom)" if qty > 1 else ""
    return {"ok": True, "status": "confirmed", "charge_usd": total, "item": item,
            "summary": f"{pkg['name']} added for {r['nights']} nights × {qty}{rule} - {money(total)}."}


async def book_spa_treatment(guest_id: str, treatment_id: str, date: str, time: str = "10:00") -> dict:
    p = await load_profile(guest_id)
    s = C.SPA_BY_ID.get(treatment_id)
    if not s:
        raise ToolError(f"Unknown treatment '{treatment_id}'")
    if date not in _sailing_dates(p)[1:-1] and date not in _sailing_dates(p)[:1]:
        raise ToolError("Pick a day during your sailing")
    sea_day = any(d["date"] == date and d["type"] == "sea" for d in p["reservation"]["ports"])
    price = s["price"] if sea_day else round(s["price"] * 0.8)
    item = _item("spa", s["name"], treatment_id=treatment_id, date=date, time=time, charge_usd=price,
                 port_day_discount=not sea_day)
    await record_booking([guest_id], item)
    p.setdefault("purchased_for_sailing", {}).setdefault("spa", []).append(treatment_id)
    await save_profiles({guest_id: p})
    await after_change([guest_id])
    return {"ok": True, "status": "confirmed", "charge_usd": price, "item": item,
            "summary": f"{s['name']} booked for {date} at {time} - {money(price)}"
                       + ("" if sea_day else " (20% port-day savings applied)") + "."}


async def complete_online_checkin(guest_id: str, arrival_slot: str) -> dict:
    p = await load_profile(guest_id)
    if arrival_slot not in C.ARRIVAL_SLOTS:
        raise ToolError(f"Arrival times available: {', '.join(C.ARRIVAL_SLOTS)}")
    dts = days_to_sail(p)
    if dts > 45:
        raise ToolError("Online check-in opens 45 days before sailing")
    party = party_ids(p)
    updates = {}
    for gid in party:
        gp = p if gid == guest_id else await store.get("profiles", profile_id(gid))
        if gp:
            gp["reservation"]["checkin_status"] = "complete"
            gp["reservation"]["arrival_slot"] = arrival_slot
            updates[gid] = gp
    await save_profiles(updates)
    item = _item("checkin", f"OceanReady · arrival {arrival_slot}", arrival_slot=arrival_slot,
                 date=p["reservation"]["embark_date"], time=arrival_slot, charge_usd=0)
    await record_booking(party, item)
    await after_change(party)
    return {"ok": True, "status": "confirmed", "charge_usd": 0, "item": item,
            "summary": f"You're checked in! {len(updates)} guest{'s' if len(updates) > 1 else ''} arriving at "
                       f"{arrival_slot} on {p['reservation']['embark_date']}. Your Medallion boarding pass is in My Cruise."}


TOOLS = {
    "get_guest_context": get_guest_context,
    "get_upgrade_offers": get_upgrade_offers,
    "place_upgrade_bid": place_upgrade_bid,
    "purchase_cabin_upgrade": purchase_cabin_upgrade,
    "apply_goodwill_upgrade": apply_goodwill_upgrade,
    "search_shore_excursions": search_shore_excursions,
    "book_shore_excursion": book_shore_excursion,
    "reserve_specialty_dining": reserve_specialty_dining,
    "purchase_package": purchase_package,
    "book_spa_treatment": book_spa_treatment,
    "complete_online_checkin": complete_online_checkin,
}
READ_ONLY_TOOLS = {"get_guest_context", "get_upgrade_offers", "search_shore_excursions"}
