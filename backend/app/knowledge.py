"""Knowledge Base documents published to AOM by the daily loader.

Two kinds:

* **Guest profile** - one per passenger sailing soon, rendered from that
  morning's Databricks row as plain prose. The concierge retrieves it with a
  `document_id`-scoped search, so a guest's question can only ever be
  grounded in *their own* profile, never a neighbour's that happens to be
  semantically close.
* **Guest Services Playbook** - fleet, policy and product knowledge (Princess Upgrade
  rules, packages, check-in, dining, ports). Contains no personal data, so
  answers grounded only in it are safe to share across guests through AOM's
  LLM cache.

FAQ entries are also synced to the phone inside the catalog document, so the
app can answer the common questions offline from Couchbase Lite.
"""
from __future__ import annotations

from . import catalog as C

FAQ = [
    {"q": "What time should I arrive at the terminal?",
     "a": "Arrive with the group you picked when you completed OceanReady check-in - it's on your Medallion boarding pass in "
          "the app. Boarding typically opens around 10:30am and all guests must be on board 90 minutes before departure. "
          "If your Medallion was shipped to you, wear it to walk straight on board.",
     "keywords": ["arrive", "arrival", "terminal", "boarding", "board", "what time"]},
    {"q": "How does Princess Upgrade work?",
     "a": "Princess Upgrade lets you bid per person, per night for an upgrade to a higher stateroom category. You're only charged if "
          "your bid is accepted, and you can change or cancel it until bidding closes about 48 hours before sailing. "
          "If you'd rather not wait, an instant upgrade confirms right away at the listed price.",
     "keywords": ["princess upgrade", "upgrade bid", "bid", "upgrade", "how does"]},
    {"q": "Who needs a beverage package?",
     "a": "If one adult (21+) in a stateroom buys Princess Plus or Princess Premier, every adult in that stateroom must have "
          "the same package. Guests under 21 can choose the Zero-Alcohol Package instead.",
     "keywords": ["beverage", "drink", "plus", "alcohol", "package", "cocktail"]},
    {"q": "What's included in Princess Premier?",
     "a": "Princess Premier bundles the Premier Beverage Package (drinks up to $20), MedallionNet Wi-Fi for up to four "
          "devices, unlimited specialty dining, reserved seats at the production shows, unlimited casual dining, digital "
          "photos and crew appreciation. Princess Plus is the lighter bundle: drinks up to $15, one-device Wi-Fi, two casual "
          "meals and crew appreciation.",
     "keywords": ["premier", "princess premier", "plus", "bundle"]},
    {"q": "Is Wi-Fi available on board?",
     "a": "Yes - MedallionNet Max is the best Wi-Fi at sea. It's included with Princess Plus (one device) and Princess "
          "Premier (four devices), or buy it per device for the whole voyage in the app; it's cheaper before you board.",
     "keywords": ["wifi", "wi-fi", "internet", "medallionnet", "medallion", "online", "connect"]},
    {"q": "Can I change my dining time?",
     "a": "Dine My Way lets you reserve a different main-dining time each night in the app before sailing or on board, "
          "or keep a traditional fixed seating. Specialty restaurants are booked separately and include a cover charge.",
     "keywords": ["dining time", "main dining", "dine my way", "dinner time", "traditional"]},
    {"q": "What do I need for check-in?",
     "a": "Get OceanReady in the app: confirm your travel documents, add a security photo, choose an arrival group and "
          "set up your onboard account. Your Medallion is shipped to your home or waiting at the terminal; bring the same "
          "travel documents with you.",
     "keywords": ["check-in", "check in", "checkin", "documents", "passport", "oceanready", "medallion"]},
    {"q": "Are kids' activities included?",
     "a": "Camp Discovery youth centers are included in your fare: The Treehouse for ages 3-7, The Lodge for 8-12 and "
          "The Beach House teen lounge for 13-17. Late-night group activities may carry a small hourly fee.",
     "keywords": ["kids", "children", "camp discovery", "teens", "youth"]},
    {"q": "What is Princess Cays?",
     "a": "Princess Cruises' private beach resort on Eleuthera in the Bahamas, a half mile of white sand reached by tender. "
          "The beach, barbecue lunch and pools are included; private bungalows, clamshells, snorkel gear and the floating "
          "aqua park are add-ons worth booking early.",
     "keywords": ["princess cays", "eleuthera", "private island", "bahamas"]},
    {"q": "Are spa treatments cheaper on port days?",
     "a": "Yes. Lotus Spa treatments booked for a port day are typically discounted - this app applies a 20% port-day "
          "price automatically.",
     "keywords": ["spa", "massage", "port day", "discount", "facial", "lotus", "enclave"]},
]


def playbook_markdown(export_date: str) -> str:
    lines = [f"# Princess Cruises Guest Services Playbook (published {export_date})", "",
             "Fleet, policy and product knowledge for the Princess Guest Concierge agent. Contains no guest data.", ""]
    lines += ["## Frequently asked questions", ""]
    for f in FAQ:
        lines += [f"**{f['q']}** {f['a']}", ""]
    lines += ["## Stateroom categories and upgrade policy", ""]
    for c in C.CABIN_CATEGORIES:
        perks = ", ".join(C.CATEGORY_PERKS.get(c["code"], [])) or "standard amenities"
        lines.append(f"- {c['name']} ({c['code']}): fares from about ${c['base_ppn']} per person per night; {perks}.")
    lines += ["", "Princess Upgrade minimum bids per person per night by number of category steps: "
              + ", ".join(f"{k} step{'s' if k > 1 else ''} ${v}" for k, v in C.UPGRADE_BID_MIN_PPN.items()) + ".",
              "Instant upgrades are priced at roughly 82% of the fare difference and confirm immediately, subject to "
              "inventory. Upgrades apply to the whole stateroom party. Complimentary (goodwill) upgrades are a service "
              "recovery gesture that always requires supervisor approval.", ""]
    lines += ["## Packages", ""]
    for p in C.PACKAGES:
        lines.append(f"- {p['name']} ({p['code']}): ${p['price_per_day']} per {p['per']}. {p['blurb']}")
    lines += ["", "## Specialty dining", ""]
    for d in C.DINING:
        ships = "fleetwide" if d["ships"] == "*" else "on " + ", ".join(C.SHIPS[s]["name"] for s in d["ships"])
        lines.append(f"- {d['name']}: {d['cuisine']}, ${d['price_pp']} per guest, {ships}.")
    lines += ["", "## Ships", ""]
    for code, s in C.SHIPS.items():
        lines.append(f"- {s['name']} ({s['class']} class), sails from {C.PORTS[s['home_port']]}. Neighborhoods: "
                     + ", ".join(s["neighborhoods"]) + ".")
    lines += ["", "## Ports and shore excursions", ""]
    for port, name in C.PORTS.items():
        exs = [e for e in C.EXCURSIONS if e["port"] == port]
        if not exs:
            continue
        lines.append(f"### {name}")
        for e in exs:
            lines.append(f"- {e['name']} ({e['id']}): ${e['price']} per guest, {e['duration_hrs']} hours, "
                         f"{e['activity']} activity; good for {', '.join(e['tags'])}.")
        lines.append("")
    lines += ["## Lotus Spa", ""]
    for s in C.SPA:
        lines.append(f"- {s['name']}: ${s['price']}" + (f", {s['minutes']} minutes." if s["minutes"] else "."))
    return "\n".join(lines)


def guest_profile_markdown(p: dict) -> str:
    r = p["reservation"]
    s = p["ml_scores"]
    prefs = p["preferences"]
    party = "; ".join(f"{m['name']} ({m['relationship']}, age {m['age_band']})" for m in r["party"])
    ports = ", ".join(f"day {d['day']} {d['date']} {d['port']}" for d in r["ports"])
    past = p["history"]["past_sailings"][:5]
    past_txt = "; ".join(f"{h['ship_name']} {h['sail_date'][:7]} {h['nights']} nights in {h['cabin_class']}, spent "
                         f"${h['onboard_spend_usd']:,.0f}" for h in past) or "first cruise with us"
    mix = p.get("onboard_spend_mix", {})
    top_mix = ", ".join(f"{k} {v:.0%}" for k, v in sorted(mix.items(), key=lambda kv: -kv[1])[:3])
    owned = p.get("purchased_for_sailing", {})
    return "\n".join([
        f"# Guest profile {p['guest_id']}: {p['first_name']} {p['last_name']}",
        f"Source: Databricks daily dump {p['export_date']}, model {s.get('model_version')}.",
        "",
        "## Upcoming sailing",
        f"{p['first_name']} sails on {r['ship_name']} - {r['itinerary_name']} - from {r['embark_port']} on "
        f"{r['embark_date']} returning {r['debark_date']} ({r['nights']} nights), booking {r['booking_id']}. "
        f"Stateroom {r['stateroom']['stateroom_number']}, {r['stateroom']['category_name']} on deck "
        f"{r['stateroom']['deck']} ({r['stateroom']['neighborhood']}, {r['stateroom']['location']}). "
        f"Check-in status: {r['checkin_status']}. Dining: {r['dining_assignment']}.",
        f"Traveling party ({r['party_size']}): {party}.",
        f"Itinerary: {ports}.",
        "",
        "## Loyalty and history",
        f"Captain's Circle {p['loyalty']['tier']} with {p['loyalty']['points']} points and "
        f"{p['loyalty']['cruises_completed']} completed cruises. Past sailings: {past_txt}. "
        f"Average onboard spend ${p['history']['avg_onboard_spend_usd']:,.0f}; accepted "
        f"{p['history']['upgrades_accepted']} upgrades and placed {p['history']['upgrade_bids_placed']} Princess Upgrade bids before.",
        f"Onboard spend mix (top): {top_mix}.",
        "",
        "## Preferences",
        f"Interests: {', '.join(prefs['interests'])}. Dietary: {', '.join(prefs['dietary']) or 'none noted'}. "
        f"Celebrating: {prefs.get('celebration') or 'nothing noted'}. Bed: {prefs['bed_configuration']}, "
        f"pillow {prefs['pillow']}. Stateroom location preference: {prefs.get('stateroom_location_pref') or 'none'}. "
        f"Travels with kids: {'yes' if prefs.get('travels_with_kids') else 'no'}. "
        f"Prefers {prefs['communication_channel']} messages.",
        "",
        "## Personalization signals",
        f"Segment: {s.get('segment')}. Next best action: {s.get('next_best_action')}. "
        f"Upgrade propensity {s.get('upgrade_propensity')}, recommended upgrade category "
        f"{s.get('recommended_upgrade_category')} with a suggested Princess Upgrade bid of ${s.get('recommended_bid_per_night_usd')} "
        f"per person per night. Price sensitivity {s.get('price_sensitivity')}. Propensities - beverage package "
        f"{s.get('beverage_package_propensity')}, specialty dining {s.get('specialty_dining_propensity')}, excursions "
        f"{s.get('excursion_propensity')}, spa {s.get('spa_propensity')}, internet {s.get('wifi_propensity')}, "
        f"Princess Premier {s.get('premier_propensity')}.",
        f"Already purchased for this sailing: packages {owned.get('packages') or 'none'}, excursions "
        f"{owned.get('excursions') or 'none'}.",
    ])
