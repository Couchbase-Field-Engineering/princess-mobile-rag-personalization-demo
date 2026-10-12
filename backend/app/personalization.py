"""Ranks the "For You" offers for one guest.

Inputs are the Databricks model scores and preferences from the daily dump,
plus live state the dump can't know about: what the guest has booked since
(bookings), unsold stateroom inventory, and how close the sailing is.
The result is written to `offers::<guest_id>`, which Sync Gateway replicates
to the guest's phone - so the For You feed renders from Couchbase Lite, even
offline, and re-ranks itself on the next sync after every booking.
"""
from __future__ import annotations

from . import catalog as C
from .docs import days_to_sail, guest_channel, now_iso, offers_id, profile_id
from .store import store

PALETTES = {  # gradient keys the app maps to brand gradients
    "upgrade": "suite", "excursion": "ocean", "dining": "dining", "package": "drinks", "spa": "spa", "checkin": "deck",
}


def _reason_list(*parts):
    return " · ".join([p for p in parts if p])


async def compute_offers(profile: dict) -> list[dict]:
    from .actions import get_inventory  # avoid import cycle

    r = profile["reservation"]
    s = profile["ml_scores"]
    prefs = profile["preferences"]
    owned = profile.get("purchased_for_sailing", {})
    dts = days_to_sail(profile)
    offers: list[dict] = []
    if not profile.get("consent", {}).get("personalization_opt_in", True):
        return offers

    # --- check-in -------------------------------------------------------
    if r["checkin_status"] != "complete" and 0 <= dts <= 45:
        offers.append({
            "offer_id": "checkin", "kind": "checkin", "palette": PALETTES["checkin"],
            "title": "Check in & pick your arrival time",
            "subtitle": f"Sailing in {dts} day{'s' if dts != 1 else ''} - get your SetSail Pass",
            "reason": "Required before boarding" + (" · popular slots are filling" if dts <= 10 else ""),
            "price_label": "Free", "score": 1.0 + (0.5 if dts <= 7 else 0),
            "cta": {"label": "Check in", "screen": "checkin"},
        })

    # --- stateroom upgrade -------------------------------------------------
    rec = s.get("recommended_upgrade_category")
    cur_rank = C.CATEGORY_BY_CODE[r["stateroom"]["category_code"]]["rank"]
    if rec and C.CATEGORY_BY_CODE[rec]["rank"] <= cur_rank:
        # Already upgraded past the model's pick since the dump - offer the next step up instead.
        rec = C.CABIN_CATEGORIES[cur_rank]["code"] if cur_rank < len(C.CABIN_CATEGORIES) else None
        s = {**s, "recommended_bid_per_night_usd": None}
    if rec and dts >= 0:
        inv, _ = await get_inventory(r["sailing_id"])
        if inv["available"].get(rec, 0) > 0:
            cur = r["stateroom"]["category_code"]
            min_bid = C.royalup_min_bid(cur, rec)
            ppn = C.upgrade_price_ppn(cur, rec)
            bid = s.get("recommended_bid_per_night_usd") or min_bid
            reason = _reason_list(
                f"Only {inv['available'][rec]} left" if inv["available"][rec] <= 3 else None,
                f"Perfect for your {prefs['celebration']}" if prefs.get("celebration") else None,
                f"{profile['loyalty']['tier']} member" if profile["loyalty"]["tier"] not in ("Gold",) else None,
            )
            offers.append({
                "offer_id": f"upgrade-{rec}", "kind": "upgrade", "palette": PALETTES["upgrade"],
                "title": f"Upgrade to {C.a_or_an(C.CATEGORY_BY_CODE[rec]['name'])}",
                "subtitle": f"Bid from ${min_bid}/night with RoyalUp, or upgrade now for ${ppn}/night",
                "reason": reason or "Your upgrade pick for this sailing",
                "price_label": f"Suggested bid ${bid}/person/night",
                "score": s.get("upgrade_propensity", 0) * (1.15 if dts <= 14 else 1.0),
                "cta": {"label": "See upgrade options", "screen": "upgrade", "args": {"category_code": rec, "bid": bid}},
                # Everything the Upgrade screen needs, so it works offline from Couchbase Lite.
                "options": [{
                    "category_code": c["code"], "category_name": c["name"], "available": inv["available"].get(c["code"], 0),
                    "instant_price_ppn": C.upgrade_price_ppn(cur, c["code"]),
                    "instant_total_usd": C.upgrade_price_ppn(cur, c["code"]) * r["nights"] * r["party_size"],
                    "royalup_min_bid_ppn": C.royalup_min_bid(cur, c["code"]),
                    "perks": C.CATEGORY_PERKS.get(c["code"], []), "recommended": c["code"] == rec,
                    "recommended_bid_ppn": bid if c["code"] == rec else None,
                } for c in C.CABIN_CATEGORIES if cur_rank < c["rank"] <= cur_rank + 3],
                "nights": r["nights"], "party_size": r["party_size"],
            })

    # --- packages ------------------------------------------------------------
    for pkg in C.PACKAGES:
        if pkg["code"] in owned.get("packages", []):
            continue
        if pkg["code"] == "REFRESH" and "DELUXE_BEV" in owned.get("packages", []):
            continue
        if pkg["code"] in ("DELUXE_BEV",) and profile["age_band"] in ("0-2", "3-5", "6-11", "12-17"):
            continue
        prop = s.get(pkg["propensity"], 0)
        if pkg["code"] == "REFRESH":
            prop = prop * 0.6 if s.get("price_sensitivity", 0.5) > 0.5 else prop * 0.35
        if pkg["code"] == "ULT_DINING":
            prop *= 0.8
        offers.append({
            "offer_id": f"package-{pkg['code']}", "kind": "package", "palette": PALETTES["package"],
            "title": pkg["name"], "subtitle": pkg["blurb"],
            "reason": {"DELUXE_BEV": "Based on what you've enjoyed on past sailings",
                       "VOOM": "Stay connected at sea", "THE_KEY": "Skip the lines" + (" with the kids" if prefs.get("travels_with_kids") else ""),
                       "ULT_DINING": "You love specialty dining", "REFRESH": "All the mocktails & lattes you want"}.get(pkg["code"], ""),
            "price_label": f"${pkg['price_per_day']} {pkg['per']}", "score": prop * 0.85,
            "cta": {"label": "Add to my cruise", "tool": "purchase_package", "args": {"package_code": pkg["code"]}},
        })

    # --- shore excursions ------------------------------------------------------
    port_days = {d["port_code"]: d for d in r["ports"] if d["type"] == "port"}
    likes = set(prefs["interests"])
    ex_scored = []
    for e in C.EXCURSIONS:
        if e["port"] not in port_days or e["id"] in owned.get("excursions", []):
            continue
        if "adults" in e["tags"] and prefs.get("travels_with_kids"):
            continue
        match = likes & set(e["tags"])
        if not match:
            continue
        ex_scored.append((len(match), e, sorted(match)))
    ex_scored.sort(key=lambda x: (-x[0], x[1]["price"]))
    seen_ports = set()
    for n, e, match in ex_scored:
        if e["port"] in seen_ports:
            continue
        seen_ports.add(e["port"])
        offers.append({
            "offer_id": f"excursion-{e['id']}", "kind": "excursion", "palette": PALETTES["excursion"],
            "title": e["name"], "subtitle": f"{C.PORTS[e['port']]} · {port_days[e['port']]['date']} · {e['duration_hrs']}h",
            "reason": f"Because you love {' & '.join(match[:2])}",
            "price_label": f"${e['price']} per guest", "score": s.get("excursion_propensity", 0) * (0.6 + 0.15 * n),
            "cta": {"label": "Book for my party", "tool": "book_shore_excursion", "args": {"excursion_id": e["id"]}},
        })
        if len(seen_ports) >= 3:
            break

    # --- specialty dining -------------------------------------------------------
    dining = [d for d in C.DINING if C.ship_has_dining(r["ship_code"], d["id"]) and d["id"] not in owned.get("dining", [])]
    def dscore(d):
        sc = 0.0
        if prefs.get("celebration") and "celebration" in d["tags"]:
            sc += 0.4
        if prefs.get("travels_with_kids") and "family" in d["tags"]:
            sc += 0.3
        if prefs.get("travels_with_kids") and "adults" in d["tags"]:
            sc -= 1
        sc += 0.2 * len(likes & set(d["tags"]))
        return sc
    dining.sort(key=dscore, reverse=True)
    for d in dining[:2]:
        offers.append({
            "offer_id": f"dining-{d['id']}", "kind": "dining", "palette": PALETTES["dining"],
            "title": d["name"], "subtitle": f"{d['cuisine']} · ${d['price_pp']} per guest",
            "reason": f"Celebrate your {prefs['celebration']} here" if prefs.get("celebration") and "celebration" in d["tags"]
            else ("A family favorite" if "family" in d["tags"] and prefs.get("travels_with_kids") else "Picked for your taste"),
            "price_label": f"${d['price_pp']} pp", "score": s.get("specialty_dining_propensity", 0) * (0.7 + dscore(d) * 0.3),
            "cta": {"label": "Reserve a table", "screen": "dining", "args": {"restaurant_id": d["id"]}},
        })

    # --- spa ---------------------------------------------------------------------
    if profile["age_band"] not in ("0-2", "3-5", "6-11", "12-17"):
        pick = "SPA-COUPLES" if prefs.get("celebration") in ("anniversary", "honeymoon") else (
            "SPA-THERMAL" if "wellness" in likes else "SPA-HOTSTONE")
        if pick not in owned.get("spa", []):
            sp = C.SPA_BY_ID[pick]
            offers.append({
                "offer_id": f"spa-{pick}", "kind": "spa", "palette": PALETTES["spa"],
                "title": sp["name"], "subtitle": f"Vitality Spa · {sp['minutes']} min" if sp["minutes"] else "Vitality Spa · all sailing",
                "reason": "Save 20% on port days", "price_label": f"from ${round(sp['price'] * 0.8)}",
                "score": s.get("spa_propensity", 0) * 0.9,
                "cta": {"label": "Choose a time", "screen": "spa", "args": {"treatment_id": pick}},
            })

    offers.sort(key=lambda o: o["score"], reverse=True)
    for i, o in enumerate(offers):
        o["rank"] = i + 1
        o["score"] = round(o["score"], 3)
    return offers


async def refresh_offers(guest_id: str) -> dict | None:
    profile = await store.get("profiles", profile_id(guest_id))
    if not profile:
        return None
    offers = await compute_offers(profile)
    doc = {
        "type": "offers", "guest_id": guest_id, "offers": offers,
        "model_version": profile["ml_scores"].get("model_version"),
        "segment": profile["ml_scores"].get("segment"),
        "export_date": profile.get("export_date"), "profile_rev": profile.get("rev", 0),
        # Fully booked dining seatings, so the dining screen only offers open ones.
        "dining_full": C.dining_availability(profile["reservation"]),
        "generated_at": now_iso(), "channels": [guest_channel(guest_id)],
    }
    await store.upsert("offers", offers_id(guest_id), doc)
    return doc
