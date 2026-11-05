#!/usr/bin/env python3
"""Generate a mock Databricks daily dump of cruise passenger reservation data.

Writes the exact layout a Databricks job produces with
`df.repartition(n).write.mode("overwrite").json(path)`:

    data/databricks-dump/dt=2026-10-09/
        part-00000-<uuid>-c000.json      # JSON Lines, one passenger reservation per line
        part-00001-<uuid>-c000.json
        ...
        _SUCCESS
        _manifest.json                   # row/byte counts + schema version (written by the notebook)

Each line is one passenger on one upcoming reservation, joined with that
guest's loyalty status, preferences, sailing history, onboard-spend profile,
what they've already purchased for this sailing, and the scores the
personalization model (pcl-personalization-v4.2) produced in Databricks.

Fully deterministic for a given --seed and --export-date, and standard
library only (runs anywhere Python 3.9+ does). Default target is 100 MiB.

    python databricks/generate_mock_dump.py                 # today, 100 MiB
    python databricks/generate_mock_dump.py --export-date 2026-10-09 --target-mb 100
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
from app import catalog as C  # noqa: E402

SCHEMA_VERSION = "guest_personalization_v3"
MODEL_VERSION = "pcl-personalization-v4.2"

FIRST = ["Olivia", "Liam", "Emma", "Noah", "Ava", "Elijah", "Sophia", "James", "Isabella", "Lucas", "Mia", "Mason",
         "Amelia", "Ethan", "Harper", "Logan", "Evelyn", "Aiden", "Abigail", "Jackson", "Emily", "Sebastian", "Ella",
         "Mateo", "Scarlett", "Daniel", "Grace", "Henry", "Chloe", "Owen", "Camila", "Wyatt", "Aria", "Carter", "Riley",
         "Jayden", "Nora", "Gabriel", "Lily", "Julian", "Zoey", "Leo", "Hannah", "David", "Layla", "Joseph", "Priya",
         "Arjun", "Mei", "Hiroshi", "Fatima", "Omar", "Sofia", "Diego", "Valentina", "Carlos", "Lucia", "Andre", "Aaliyah",
         "Marcus", "Keisha", "Tyrone", "Ngozi", "Kwame", "Siobhan", "Declan", "Ingrid", "Lars", "Anika", "Ravi"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee",
        "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
        "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker",
        "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts", "Patel", "Shah", "Kim", "Chen", "Okafor",
        "O'Brien", "Kowalski", "Nakamura", "Fischer", "Rossi", "Bennett", "Natarajan", "Haddad", "Silva"]
CITIES = [("Orlando", "FL", "US"), ("Miami", "FL", "US"), ("Tampa", "FL", "US"), ("Atlanta", "GA", "US"),
          ("Charlotte", "NC", "US"), ("Dallas", "TX", "US"), ("Houston", "TX", "US"), ("Austin", "TX", "US"),
          ("Chicago", "IL", "US"), ("Columbus", "OH", "US"), ("New York", "NY", "US"), ("Newark", "NJ", "US"),
          ("Philadelphia", "PA", "US"), ("Boston", "MA", "US"), ("Nashville", "TN", "US"), ("Denver", "CO", "US"),
          ("Phoenix", "AZ", "US"), ("Los Angeles", "CA", "US"), ("San Diego", "CA", "US"), ("Seattle", "WA", "US"),
          ("Toronto", "ON", "CA"), ("Montreal", "QC", "CA"), ("London", "", "GB"), ("Manchester", "", "GB"),
          ("Mexico City", "", "MX"), ("San Juan", "PR", "US")]
DIETARY = ["vegetarian", "vegan", "gluten-free", "pescatarian", "kosher", "halal", "dairy-free"]
CELEBRATIONS = ["anniversary", "birthday", "honeymoon", "retirement", "graduation", "family reunion"]
CHANNELS = ["princess.com", "travel_advisor", "call_center", "medallionclass_app"]
AGE_BANDS = ["0-2", "3-5", "6-11", "12-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]
INTEREST_POOL = [i for i in C.INTERESTS]


def clamp(x: float, lo=0.01, hi=0.99) -> float:
    return round(max(lo, min(hi, x)), 3)


class Gen:
    def __init__(self, export_date: dt.date, seed: int):
        self.d0 = export_date
        self.r = random.Random(seed)
        self.guest_seq = 100000
        self.booking_seq = 4800000
        self.sailings = self._sailings()

    # -- sailings -----------------------------------------------------------
    def _sailings(self):
        out = []
        for code, ship in C.SHIPS.items():
            itins = C.SHIP_ITINERARIES[code]
            day = self.d0 - dt.timedelta(days=self.d0.weekday())  # Monday this week
            i = 0
            while day < self.d0 + dt.timedelta(days=150):
                itin_code = itins[i % len(itins)]
                itin = C.ITINERARIES[itin_code]
                # 7-night (and longer) sailings leave Sundays, short ones Fri (3n) / Mon (4n)
                offset = {7: 6, 3: 4, 4: 0}.get(itin["nights"], 6)
                embark = day + dt.timedelta(days=offset)
                if embark > self.d0:
                    out.append(self._sailing(code, itin_code, embark))
                day += dt.timedelta(days=7)
                i += 1
        return out

    def _sailing(self, ship_code, itin_code, embark):
        itin = C.ITINERARIES[itin_code]
        home = C.SHIPS[ship_code]["home_port"]
        ports = []
        for n, p in enumerate(itin["days"]):
            code = home if p in ("EMB", "DEB") else p
            date = embark + dt.timedelta(days=n)
            ports.append({
                "day": n + 1, "date": date.isoformat(), "port_code": code, "port": C.PORTS[code],
                "arrive": None if p in ("EMB", "SEA") else ("07:00" if p == "DEB" else "08:00"),
                "depart": None if p in ("DEB", "SEA") else ("16:30" if p == "EMB" else "17:00"),
                "type": {"EMB": "embark", "DEB": "debark", "SEA": "sea"}.get(p, "port"),
            })
        return {
            "sailing_id": f"{ship_code}-{embark:%Y%m%d}",
            "ship_code": ship_code, "ship_name": C.SHIPS[ship_code]["name"],
            "itinerary_code": itin_code, "itinerary_name": itin["name"], "nights": itin["nights"],
            "embark_port_code": home, "embark_port": C.PORTS[home],
            "embark_date": embark.isoformat(),
            "debark_date": (embark + dt.timedelta(days=itin["nights"])).isoformat(),
            "ports": ports,
        }

    def pick_sailing(self):
        # Near-term sailings are over-represented: they are the ones the app
        # is actively personalizing (pre-cruise planner window).
        r = self.r
        horizon = 150 if r.random() < 0.55 else 30
        while True:
            s = r.choice(self.sailings)
            days = (dt.date.fromisoformat(s["embark_date"]) - self.d0).days
            if days <= horizon:
                return s

    def find_sailing(self, ship_code, days_out):
        """The demo personas' sailing: exactly `days_out` days after the export
        date, whatever weekday that is, so the story ("Olivia sails in 9 days")
        is the same in every daily export. Same itinerary as the ship's nearest
        scheduled sailing."""
        target = self.d0 + dt.timedelta(days=days_out)
        best = min((s for s in self.sailings if s["ship_code"] == ship_code),
                   key=lambda s: abs((dt.date.fromisoformat(s["embark_date"]) - target).days))
        if best["embark_date"] == target.isoformat():
            return best
        return self._sailing(ship_code, best["itinerary_code"], target)

    # -- people -------------------------------------------------------------
    def next_guest_id(self):
        self.guest_seq += 1
        return f"G{self.guest_seq:08d}"

    def next_booking(self):
        self.booking_seq += self.r.randint(1, 37)
        return f"{self.booking_seq}"

    def tier_for(self, cruises):
        pts = cruises * 9 + self.r.randint(0, 9) if cruises else 0
        tier = "Gold"
        for t in C.LOYALTY_TIERS:
            if pts >= C.LOYALTY_THRESHOLDS[t]:
                tier = t
        return tier, pts

    def history(self, cruises, base_class_rank):
        r = self.r
        past = []
        for k in range(min(cruises, 12)):
            ship = r.choice(list(C.SHIPS))
            nights = r.choice([3, 4, 5, 7, 7, 7, 9])
            when = self.d0 - dt.timedelta(days=r.randint(120, 365 * 12))
            rank = max(1, min(7, base_class_rank + r.choice([-1, 0, 0, 0, 1])))
            spend = round(nights * r.uniform(60, 420) * (0.7 + rank * 0.18), 2)
            past.append({
                "ship_code": ship, "ship_name": C.SHIPS[ship]["name"], "sail_date": when.isoformat(),
                "nights": nights, "cabin_class": C.CABIN_CATEGORIES[rank - 1]["name"],
                "onboard_spend_usd": spend,
                "excursions_booked": r.randint(0, 4), "specialty_dining_nights": r.randint(0, nights),
                "nps": r.choice([6, 7, 8, 9, 9, 10, 10, None]),
            })
        past.sort(key=lambda p: p["sail_date"], reverse=True)
        return past

    def row(self, s, booking_id, party, me, lead, cabin, booked_date, overrides=None):
        r = self.r
        cruises = me["cruises"]
        tier, pts = self.tier_for(cruises)
        past = self.history(cruises, C.CATEGORY_BY_CODE[cabin["category_code"]]["rank"])
        avg_spend = round(sum(p["onboard_spend_usd"] for p in past) / len(past), 2) if past else 0.0
        interests = me["interests"]
        adult = me["age_band"] not in ("0-2", "3-5", "6-11", "12-17")
        price_sens = clamp(r.gauss(0.5, 0.2) - (0.05 * C.LOYALTY_TIERS.index(tier)))
        spend_mix = [r.random() for _ in range(6)]
        tot = sum(spend_mix)
        spend_mix = [round(x / tot, 3) for x in spend_mix]
        has_kids = any(p["age_band"] in ("0-2", "3-5", "6-11", "12-17") for p in party)
        rank = C.CATEGORY_BY_CODE[cabin["category_code"]]["rank"]
        up_prop = clamp(0.25 + 0.08 * min(cruises, 5) + (0.12 if me.get("celebration") else 0)
                        - 0.3 * price_sens + r.gauss(0, 0.12) - (0.04 * max(0, rank - 4)))
        rec_rank = min(7, rank + (2 if up_prop > 0.75 and rank <= 3 else 1))
        rec_code = C.CABIN_CATEGORIES[rec_rank - 1]["code"]
        min_bid = C.upgrade_bid_min(cabin["category_code"], rec_code) if rank < 7 else 0
        rec_bid = int(round(min_bid * (1.15 + (1 - price_sens) * 0.6) / 5) * 5) if min_bid else 0
        if min_bid:
            rec_bid = max(min_bid, min(rec_bid, C.upgrade_price_ppn(cabin["category_code"], rec_code) - 5))

        scores = {
            "model_version": MODEL_VERSION,
            "scored_at": f"{self.d0.isoformat()}T05:12:44Z",
            "upgrade_propensity": up_prop if rank < 7 else 0.0,
            "price_sensitivity": price_sens,
            "beverage_package_propensity": clamp(spend_mix[0] * 1.6 + (0.2 if adult else -0.4) + r.gauss(0, 0.1)),
            "specialty_dining_propensity": clamp(spend_mix[1] * 1.5 + (0.2 if "food" in interests else 0) + r.gauss(0.1, 0.1)),
            "excursion_propensity": clamp(spend_mix[2] * 1.4 + 0.1 * len(interests) / 3 + r.gauss(0.1, 0.1)),
            "spa_propensity": clamp(spend_mix[3] * 1.5 + (0.35 if "spa" in interests else 0) + (0.1 if adult else -0.5)),
            "wifi_propensity": clamp(0.35 + (0.25 if me["age_band"] in ("12-17", "18-24", "25-34") else 0) + r.gauss(0, 0.15)),
            "premier_propensity": clamp(0.15 + (0.2 if has_kids else 0) + 0.1 * (1 - price_sens) + r.gauss(0, 0.1)),
            "casino_propensity": clamp(spend_mix[4] * 1.3 + (0 if adult else -1)),
            "churn_risk": clamp(0.35 - 0.04 * min(cruises, 8) + r.gauss(0, 0.08)),
            "predicted_onboard_spend_usd": round(avg_spend * r.uniform(0.85, 1.25) if avg_spend else s["nights"] * r.uniform(90, 260), 2),
            "recommended_upgrade_category": rec_code if rank < 7 else None,
            "recommended_bid_per_night_usd": rec_bid,
            "segment": r.choice(["Family Thrill Seekers", "Luxury Celebrators", "Value Explorers", "Wellness Escapers",
                                 "Foodie Couples", "Party Weekenders", "Loyal Cruisers", "First-Time Families"]),
        }
        nba = max(
            [("upgrade_bid", scores["upgrade_propensity"]),
             ("beverage_package", scores["beverage_package_propensity"]),
             ("shore_excursion", scores["excursion_propensity"]),
             ("specialty_dining", scores["specialty_dining_propensity"]),
             ("spa", scores["spa_propensity"])], key=lambda x: x[1])[0]
        scores["next_best_action"] = nba

        days_out = (dt.date.fromisoformat(s["embark_date"]) - self.d0).days
        purchased = {"packages": [], "excursions": [], "dining": [], "spa": []}
        if r.random() < 0.18:
            purchased["packages"].append(r.choice(["MEDALLIONNET", "PLUS", "PLUS", "ZERO_ALC", "PREMIER"]))
        if r.random() < 0.15:
            port_ex = [e for e in C.EXCURSIONS if e["port"] in {p["port_code"] for p in s["ports"]}]
            if port_ex:
                purchased["excursions"].append(r.choice(port_ex)["id"])

        row = {
            "export_date": self.d0.isoformat(),
            "schema_version": SCHEMA_VERSION,
            "guest_id": me["guest_id"],
            "captains_circle_number": f"{300000000 + int(me['guest_id'][1:]) * 7 % 699999999}",
            "first_name": me["first_name"], "last_name": me["last_name"],
            "email": f"{me['first_name'].lower()}.{me['last_name'].lower().replace(chr(39), '')}{int(me['guest_id'][1:]) % 997}@example.com"
            if adult else None,
            "age_band": me["age_band"],
            "home_city": me["city"][0], "home_state": me["city"][1], "home_country": me["city"][2],
            "preferred_language": "es" if me["city"][2] == "MX" else ("fr" if me["city"][1] == "QC" else "en"),
            "loyalty": {"program": "Captain's Circle", "tier": tier, "points": pts,
                        "cruises_completed": cruises, "member_since": str(self.d0.year - min(cruises * 2, 25) - r.randint(0, 2))},
            "reservation": {
                "booking_id": booking_id, "booking_status": "Confirmed", "booked_date": booked_date.isoformat(),
                "booking_channel": r.choice(CHANNELS), "lead_guest": lead,
                **{k: s[k] for k in ("sailing_id", "ship_code", "ship_name", "itinerary_code", "itinerary_name",
                                     "nights", "embark_port_code", "embark_port", "embark_date", "debark_date", "ports")},
                "days_to_sail": days_out,
                "party_size": len(party),
                "party": [{"guest_id": p["guest_id"], "name": f"{p['first_name']} {p['last_name']}",
                           "age_band": p["age_band"], "relationship": p["relationship"]} for p in party],
                "stateroom": cabin,
                "fare_paid_usd": round(C.CATEGORY_BY_CODE[cabin["category_code"]]["base_ppn"] * s["nights"] * r.uniform(0.85, 1.2), 2),
                "balance_due_usd": 0.0 if days_out < 90 else round(r.uniform(200, 1500), 2),
                "checkin_status": "complete" if (days_out < 14 and r.random() < 0.35) else "not_started",
                "arrival_slot": None,
                "dining_assignment": r.choice(["Dine My Way", "Traditional Dining 5:00pm", "Traditional Dining 7:15pm"]),
            },
            "preferences": {
                "interests": interests,
                "dietary": me["dietary"],
                "celebration": me.get("celebration"),
                "bed_configuration": r.choice(["queen", "two twins"]) if not has_kids else "queen + sofa bed",
                "pillow": r.choice(["standard", "firm", "memory foam"]),
                "stateroom_location_pref": r.choice(["midship", "forward", "aft", "high deck", "near elevators", None]),
                "communication_channel": r.choice(["push", "email", "sms"]),
                "travels_with_kids": has_kids,
            },
            "history": {
                "past_sailings": past,
                "avg_onboard_spend_usd": avg_spend,
                "lifetime_value_usd": round(sum(p["onboard_spend_usd"] for p in past) + cruises * r.uniform(900, 2600), 2),
                "upgrades_accepted": r.randint(0, min(cruises, 4)),
                "upgrade_bids_placed": r.randint(0, min(cruises, 6)),
                "last_nps": past[0]["nps"] if past else None,
            },
            "onboard_spend_mix": dict(zip(["beverage", "dining", "excursions", "spa", "casino", "retail"], spend_mix)),
            "purchased_for_sailing": purchased,
            "ml_scores": scores,
            "consent": {"personalization_opt_in": r.random() > 0.03, "marketing_opt_in": r.random() > 0.2},
            "_ingest": {"source_table": "pcl_prod.guest360.passenger_reservation_personalization",
                        "pipeline": "guest_personalization_daily_export", "dbr_version": "16.4 LTS"},
        }
        if overrides:
            deep_update(row, overrides)
        return row

    def person(self, last=None, age_band=None, relationship="self", city=None, first=None):
        r = self.r
        return {
            "guest_id": self.next_guest_id(),
            "first_name": first or r.choice(FIRST),
            "last_name": last or r.choice(LAST),
            "age_band": age_band or r.choice(AGE_BANDS[4:]),
            "relationship": relationship,
            "city": city or r.choice(CITIES),
            "cruises": max(0, int(r.expovariate(1 / 4.5))),
            "interests": r.sample(INTEREST_POOL, r.randint(2, 5)),
            "dietary": r.sample(DIETARY, 1) if r.random() < 0.18 else [],
            "celebration": r.choice(CELEBRATIONS) if r.random() < 0.16 else None,
        }

    def cabin(self, s, code):
        cat = C.CATEGORY_BY_CODE[code]
        deck = self.r.randint(*cat["decks"])
        num = f"{deck}{self.r.randint(100, 699):03d}"
        hood = self.r.choice(C.SHIPS[s["ship_code"]]["neighborhoods"])
        return {"stateroom_number": num, "deck": deck, "category_code": code, "category_name": cat["name"],
                "neighborhood": hood, "location": self.r.choice(["Forward", "Midship", "Aft"])}

    def booking_rows(self):
        r = self.r
        s = self.pick_sailing()
        lead = self.person()
        size = r.choices([1, 2, 2, 2, 3, 4, 4, 5], k=1)[0]
        party = [lead]
        kids = r.random() < 0.35 and size >= 3
        for n in range(size - 1):
            if n == 0:
                p = self.person(last=lead["last_name"] if r.random() < 0.7 else None, relationship="spouse/partner",
                                city=lead["city"])
            elif kids:
                p = self.person(last=lead["last_name"], age_band=r.choice(AGE_BANDS[1:4]), relationship="child",
                                city=lead["city"])
                p["cruises"] = min(p["cruises"], 3)
            else:
                p = self.person(relationship="friend/family", city=lead["city"])
            party.append(p)
        code = r.choices(["IN", "OV", "BA", "MS", "PS", "OS", "SK"], weights=[26, 16, 36, 14, 5, 2, 1])[0]
        cabin = self.cabin(s, code)
        bid = self.next_booking()
        booked = dt.date.fromisoformat(s["embark_date"]) - dt.timedelta(days=r.randint(10, 330))
        return [self.row(s, bid, party, p, i == 0, cabin, booked) for i, p in enumerate(party)]

    # -- personas -------------------------------------------------------------
    def personas(self):
        """Hand-built demo guests. Their sailings are relative to the export
        date so the demo story stays the same whenever the dump is generated."""
        rows = []

        # 1. Olivia Bennett - Captain's Circle Elite, anniversary, Sun Princess in 9 days,
        #    Balcony -> high Princess Upgrade propensity for a Mini-Suite / Premium Suite.
        s = self.find_sailing("SUN", 9)
        o = {"guest_id": "G00000101", "first_name": "Olivia", "last_name": "Bennett", "age_band": "45-54",
             "relationship": "self", "city": ("Charlotte", "NC", "US"), "cruises": 16,
             "interests": ["snorkeling", "fine dining", "spa", "live shows", "beach"], "dietary": [],
             "celebration": "anniversary"}
        d = {"guest_id": "G00000102", "first_name": "Daniel", "last_name": "Bennett", "age_band": "45-54",
             "relationship": "spouse/partner", "city": ("Charlotte", "NC", "US"), "cruises": 15,
             "interests": ["wine", "snorkeling", "history"], "dietary": ["pescatarian"], "celebration": "anniversary"}
        cab = {"stateroom_number": "9254", "deck": 9, "category_code": "BA", "category_name": "Balcony",
               "neighborhood": "Dolphin", "location": "Midship"}
        for i, p in enumerate([o, d]):
            rows.append(self.row(s, "4810101", [o, d], p, i == 0, cab, self.d0 - dt.timedelta(days=210), overrides={
                "ml_scores": {"upgrade_propensity": 0.86, "price_sensitivity": 0.22, "segment": "Luxury Celebrators",
                              "recommended_upgrade_category": "PS", "recommended_bid_per_night_usd": 135,
                              "next_best_action": "upgrade_bid", "specialty_dining_propensity": 0.81,
                              "spa_propensity": 0.77, "beverage_package_propensity": 0.64, "excursion_propensity": 0.72},
                "reservation": {"checkin_status": "not_started", "booking_channel": "mobile_app"},
                "purchased_for_sailing": {"packages": ["PLUS"], "excursions": [], "dining": [], "spa": []},
                "email": f"{p['first_name'].lower()}.bennett@example.com",
            }))

        # 2. Carlos Rivera - Gold, family of four, Caribbean Princess getaway in 3 days, Interior.
        s = self.find_sailing("CAR", 3)
        fam = [
            {"guest_id": "G00000201", "first_name": "Carlos", "last_name": "Rivera", "age_band": "35-44"},
            {"guest_id": "G00000202", "first_name": "Ana", "last_name": "Rivera", "age_band": "35-44"},
            {"guest_id": "G00000203", "first_name": "Mateo", "last_name": "Rivera", "age_band": "6-11"},
            {"guest_id": "G00000204", "first_name": "Lucia", "last_name": "Rivera", "age_band": "3-5"},
        ]
        rels = ["self", "spouse/partner", "child", "child"]
        for p, rel in zip(fam, rels):
            p.update({"relationship": rel, "city": ("Orlando", "FL", "US"), "cruises": 1 if rel != "child" else 0,
                      "interests": ["waterpark", "family", "thrill", "kids club", "beach"], "dietary": [],
                      "celebration": "birthday" if p["first_name"] == "Mateo" else None})
        cab = {"stateroom_number": "6531", "deck": 6, "category_code": "IN", "category_name": "Interior",
               "neighborhood": "Fiesta", "location": "Aft"}
        for i, p in enumerate(fam):
            rows.append(self.row(s, "4820202", fam, p, i == 0, cab, self.d0 - dt.timedelta(days=64), overrides={
                "ml_scores": {"upgrade_propensity": 0.58, "price_sensitivity": 0.66, "segment": "First-Time Families",
                              "recommended_upgrade_category": "OV", "recommended_bid_per_night_usd": 35,
                              "next_best_action": "shore_excursion", "excursion_propensity": 0.88,
                              "premier_propensity": 0.61, "beverage_package_propensity": 0.42},
                "reservation": {"checkin_status": "not_started"},
                "purchased_for_sailing": {"packages": [], "excursions": [], "dining": [], "spa": []},
                "email": f"{p['first_name'].lower()}.rivera@example.com" if rel in ("self", "spouse/partner") else None,
            }))

        # 3. Priya Natarajan - Platinum, solo wellness traveler, Star Princess in 2 days, Mini-Suite.
        s = self.find_sailing("STR", 2)
        p = {"guest_id": "G00000301", "first_name": "Priya", "last_name": "Natarajan", "age_band": "35-44",
             "relationship": "self", "city": ("Austin", "TX", "US"), "cruises": 6,
             "interests": ["spa", "wellness", "food", "wine", "sailing"], "dietary": ["vegetarian"], "celebration": None}
        cab = {"stateroom_number": "11318", "deck": 11, "category_code": "MS", "category_name": "Mini-Suite",
               "neighborhood": "Baja", "location": "Forward"}
        rows.append(self.row(s, "4830303", [p], p, True, cab, self.d0 - dt.timedelta(days=120), overrides={
            "ml_scores": {"upgrade_propensity": 0.71, "price_sensitivity": 0.31, "segment": "Wellness Escapers",
                          "recommended_upgrade_category": "PS", "recommended_bid_per_night_usd": 95,
                          "next_best_action": "spa", "spa_propensity": 0.93, "specialty_dining_propensity": 0.79,
                          "beverage_package_propensity": 0.28},
            "reservation": {"checkin_status": "complete", "arrival_slot": "12:30"},
            "purchased_for_sailing": {"packages": ["ZERO_ALC"], "excursions": [], "dining": [], "spa": []},
            "email": "priya.natarajan@example.com",
        }))
        return rows


def deep_update(base: dict, upd: dict):
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export-date", default=dt.date.today().isoformat())
    ap.add_argument("--target-mb", type=float, default=100.0, help="approximate total size in MiB")
    ap.add_argument("--parts", type=int, default=4, help="number of part files (keep each under GitHub's 50MB warning)")
    ap.add_argument("--seed", type=int, default=20261009)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "data", "databricks-dump"))
    args = ap.parse_args(argv)

    export_date = dt.date.fromisoformat(args.export_date)
    g = Gen(export_date, args.seed)
    target = int(args.target_mb * 1024 * 1024)
    per_part = target // args.parts + 1
    out_dir = os.path.abspath(os.path.join(args.out, f"dt={export_date.isoformat()}"))
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if f.startswith("part-") or f in ("_SUCCESS", "_manifest.json"):
            os.remove(os.path.join(out_dir, f))

    job_uuid = uuid.UUID(int=g.r.getrandbits(128))
    written, rows, bookings, guests_total = 0, 0, 0, 0
    files = []
    pending = g.personas()
    bookings += 3
    for part in range(args.parts):
        name = f"part-{part:05d}-{job_uuid}-c000.json"
        path = os.path.join(out_dir, name)
        part_bytes, part_rows = 0, 0
        with open(path, "w", encoding="utf-8") as fh:
            while part_bytes < per_part and written < target:
                if not pending:
                    pending = g.booking_rows()
                    bookings += 1
                line = json.dumps(pending.pop(0), separators=(",", ":"), ensure_ascii=False) + "\n"
                b = len(line.encode("utf-8"))
                fh.write(line)
                part_bytes += b
                written += b
                part_rows += 1
        rows += part_rows
        files.append({"file": name, "rows": part_rows, "bytes": part_bytes})
        print(f"  {name}  {part_rows:>7,} rows  {part_bytes / 1048576:6.1f} MiB", flush=True)
    guests_total = rows

    manifest = {
        "table": "pcl_prod.guest360.passenger_reservation_personalization",
        "export_date": export_date.isoformat(), "schema_version": SCHEMA_VERSION, "model_version": MODEL_VERSION,
        "format": "jsonl", "rows": rows, "bookings": bookings, "bytes": written, "files": files,
        "sailings": len(g.sailings), "generator": "databricks/generate_mock_dump.py", "seed": args.seed,
        "demo_personas": ["G00000101", "G00000201", "G00000301"],
    }
    with open(os.path.join(out_dir, "_manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    open(os.path.join(out_dir, "_SUCCESS"), "w").close()
    print(f"Wrote {rows:,} passenger reservations ({bookings:,} bookings, {guests_total:,} guests) "
          f"= {written / 1048576:.1f} MiB to {out_dir}")


if __name__ == "__main__":
    main()
