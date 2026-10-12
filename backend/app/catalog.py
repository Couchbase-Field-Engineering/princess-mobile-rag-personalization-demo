"""Reference catalog for the demo: ships, itineraries, stateroom categories,
shore excursions, specialty dining, packages and spa.

This is the single source of truth shared by the Databricks mock-dump
generator (databricks/generate_mock_dump.py imports it), the backend's
personalization engine and the MCP tools. Prices and names are illustrative
demo values, not live Royal Caribbean pricing.
"""
from __future__ import annotations

import hashlib

# --------------------------------------------------------------------------
# Fleet
# --------------------------------------------------------------------------
SHIPS = {
    "ICN": {"name": "Icon of the Seas", "class": "Icon", "home_port": "MIA",
            "neighborhoods": ["Central Park", "Surfside", "Thrill Island", "Chill Island", "Royal Promenade", "AquaDome"]},
    "UT": {"name": "Utopia of the Seas", "class": "Oasis", "home_port": "PCV",
           "neighborhoods": ["Central Park", "Boardwalk", "Royal Promenade", "Pool & Sports Zone", "Vitality Spa"]},
    "WN": {"name": "Wonder of the Seas", "class": "Oasis", "home_port": "PCV",
           "neighborhoods": ["Central Park", "Boardwalk", "Royal Promenade", "Suite Neighborhood", "Pool & Sports Zone"]},
    "SY": {"name": "Symphony of the Seas", "class": "Oasis", "home_port": "MIA",
           "neighborhoods": ["Central Park", "Boardwalk", "Royal Promenade", "Pool & Sports Zone"]},
    "HM": {"name": "Harmony of the Seas", "class": "Oasis", "home_port": "GAL",
           "neighborhoods": ["Central Park", "Boardwalk", "Royal Promenade", "Pool & Sports Zone"]},
    "AL": {"name": "Allure of the Seas", "class": "Oasis", "home_port": "PCV",
           "neighborhoods": ["Central Park", "Boardwalk", "Royal Promenade", "Pool & Sports Zone"]},
    "NV": {"name": "Navigator of the Seas", "class": "Voyager", "home_port": "LAX",
           "neighborhoods": ["Royal Promenade", "Pool Deck", "Vitality Spa"]},
    "ST": {"name": "Star of the Seas", "class": "Icon", "home_port": "PCV",
           "neighborhoods": ["Central Park", "Surfside", "Thrill Island", "Chill Island", "Royal Promenade", "AquaDome"]},
}

PORTS = {
    "MIA": "Miami, Florida",
    "PCV": "Port Canaveral (Orlando), Florida",
    "GAL": "Galveston, Texas",
    "LAX": "Los Angeles, California",
    "CCY": "Perfect Day at CocoCay, Bahamas",
    "NAS": "Nassau, Bahamas",
    "CZM": "Cozumel, Mexico",
    "RTB": "Roatán, Honduras",
    "CMY": "Costa Maya, Mexico",
    "STT": "Charlotte Amalie, St. Thomas",
    "SXM": "Philipsburg, St. Maarten",
    "LAB": "Labadee, Haiti",
    "FAL": "Falmouth, Jamaica",
    "ENS": "Ensenada, Mexico",
    "CAT": "Catalina Island, California",
    "SEA": "At sea",
}

# itinerary_code -> definition. `days` lists one entry per day of the sailing.
ITINERARIES = {
    "7WCPD": {"name": "7 Night Western Caribbean & Perfect Day", "nights": 7,
              "days": ["EMB", "SEA", "RTB", "CMY", "CZM", "SEA", "CCY", "DEB"]},
    "7ECPD": {"name": "7 Night Eastern Caribbean & Perfect Day", "nights": 7,
              "days": ["EMB", "SEA", "SXM", "STT", "SEA", "SEA", "CCY", "DEB"]},
    "4BAPD": {"name": "4 Night Bahamas & Perfect Day", "nights": 4,
              "days": ["EMB", "NAS", "CCY", "SEA", "DEB"]},
    "3BAPD": {"name": "3 Night Bahamas & Perfect Day Weekend", "nights": 3,
              "days": ["EMB", "NAS", "CCY", "DEB"]},
    "7WCLF": {"name": "7 Night Western Caribbean with Labadee & Falmouth", "nights": 7,
              "days": ["EMB", "SEA", "LAB", "FAL", "SEA", "CZM", "SEA", "DEB"]},
    "4BJMX": {"name": "4 Night Baja Mexico", "nights": 4,
              "days": ["EMB", "CAT", "ENS", "SEA", "DEB"]},
}

# ship -> itineraries it sails (first is the "anchor" itinerary)
SHIP_ITINERARIES = {
    "ICN": ["7WCPD", "7ECPD"],
    "UT": ["3BAPD", "4BAPD"],
    "WN": ["7ECPD", "7WCPD"],
    "SY": ["7WCPD", "7ECPD"],
    "HM": ["7WCLF", "4BAPD"],
    "AL": ["4BAPD", "3BAPD"],
    "NV": ["4BJMX"],
    "ST": ["7ECPD", "7WCPD"],
}

# --------------------------------------------------------------------------
# Staterooms. Rank is the upgrade ladder; prices are per person per night.
# --------------------------------------------------------------------------
CABIN_CATEGORIES = [
    {"code": "IN", "name": "Interior", "rank": 1, "base_ppn": 115, "decks": (2, 11)},
    {"code": "OV", "name": "Ocean View", "rank": 2, "base_ppn": 140, "decks": (3, 11)},
    {"code": "BA", "name": "Balcony", "rank": 3, "base_ppn": 185, "decks": (6, 14)},
    {"code": "JS", "name": "Junior Suite", "rank": 4, "base_ppn": 290, "decks": (8, 15)},
    {"code": "GS", "name": "Grand Suite", "rank": 5, "base_ppn": 470, "decks": (10, 16)},
    {"code": "OS", "name": "Owner's Suite", "rank": 6, "base_ppn": 690, "decks": (10, 16)},
    {"code": "RL", "name": "Royal Loft Suite", "rank": 7, "base_ppn": 1150, "decks": (15, 17)},
]
CATEGORY_BY_CODE = {c["code"]: c for c in CABIN_CATEGORIES}
CATEGORY_PERKS = {
    "BA": ["Private balcony", "Sitting area"],
    "JS": ["Priority boarding", "Suite lounge access on select ships", "Larger balcony", "Bathtub"],
    "GS": ["Star/Sky Class perks", "Coastal Kitchen dining", "Suite Sun Deck", "Priority departure"],
    "OS": ["Royal Genie service (Star Class)", "Separate living room", "Specialty dining included"],
    "RL": ["Two-story loft", "Wraparound balcony", "Royal Genie service", "Unlimited beverages & dining"],
}

# Minimum RoyalUp bid per person per night for a step of N ranks.
ROYALUP_MIN_BID_PPN = {1: 25, 2: 60, 3: 110, 4: 220, 5: 380}


def upgrade_price_ppn(from_code: str, to_code: str) -> int:
    """Instant-upgrade price (per person per night) between two categories."""
    a, b = CATEGORY_BY_CODE[from_code], CATEGORY_BY_CODE[to_code]
    delta = max(0, b["base_ppn"] - a["base_ppn"])
    # Last-minute upgrade discount, but always comfortably above the RoyalUp
    # floor - otherwise bidding would never make sense.
    price = max(delta * 0.82, royalup_min_bid(from_code, to_code) * 1.6)
    return int(round(price / 5.0) * 5)


def royalup_min_bid(from_code: str, to_code: str) -> int:
    steps = CATEGORY_BY_CODE[to_code]["rank"] - CATEGORY_BY_CODE[from_code]["rank"]
    return ROYALUP_MIN_BID_PPN.get(steps, 0)


def _h(*parts: str) -> int:
    return int(hashlib.sha1("|".join(parts).encode()).hexdigest()[:8], 16)


def initial_inventory(sailing_id: str) -> dict:
    """Deterministic unsold staterooms per category for a sailing - what the
    revenue team would release to upgrades a week or two before sailing."""
    out = {}
    for c in CABIN_CATEGORIES:
        if c["code"] == "IN":
            continue
        cap = {"OV": 14, "BA": 22, "JS": 9, "GS": 4, "OS": 2, "RL": 1}[c["code"]]
        out[c["code"]] = _h(sailing_id, c["code"]) % (cap + 1)
    # Always leave a little room in the hero categories so demos never dead-end.
    out["BA"] = max(out["BA"], 3)
    out["JS"] = max(out["JS"], 2)
    out["GS"] = max(out["GS"], 1)
    return out


# --------------------------------------------------------------------------
# Shore excursions (tags drive interest matching)
# --------------------------------------------------------------------------
EXCURSIONS = [
    # Perfect Day at CocoCay
    {"id": "CCY-THRILL", "port": "CCY", "name": "Thrill Waterpark Day Pass", "price": 89, "duration_hrs": 6,
     "tags": ["waterpark", "family", "thrill"], "activity": "high"},
    {"id": "CCY-BEACHCLUB", "port": "CCY", "name": "Coco Beach Club Day Pass", "price": 149, "duration_hrs": 6,
     "tags": ["beach", "relaxation", "luxury", "adults"], "activity": "low"},
    {"id": "CCY-HIDEAWAY", "port": "CCY", "name": "Hideaway Beach (Adults Only)", "price": 129, "duration_hrs": 6,
     "tags": ["beach", "nightlife", "adults", "relaxation"], "activity": "low"},
    {"id": "CCY-BALLOON", "port": "CCY", "name": "Up, Up and Away Helium Balloon", "price": 49, "duration_hrs": 0.5,
     "tags": ["views", "family", "photography"], "activity": "low"},
    {"id": "CCY-SNORKEL", "port": "CCY", "name": "CocoCay Snorkel Tour", "price": 69, "duration_hrs": 2,
     "tags": ["snorkeling", "ocean", "nature"], "activity": "medium"},
    # Cozumel
    {"id": "CZM-REEF", "port": "CZM", "name": "Palancar Reef Snorkel & Beach Break", "price": 79, "duration_hrs": 4,
     "tags": ["snorkeling", "ocean", "nature"], "activity": "medium"},
    {"id": "CZM-TULUM", "port": "CZM", "name": "Tulum Ruins by Ferry", "price": 139, "duration_hrs": 7,
     "tags": ["history", "culture", "photography"], "activity": "medium"},
    {"id": "CZM-TEQUILA", "port": "CZM", "name": "Tequila & Mexican Cuisine Tasting", "price": 69, "duration_hrs": 3,
     "tags": ["food", "culture", "adults"], "activity": "low"},
    # Roatan
    {"id": "RTB-ZIP", "port": "RTB", "name": "Canopy Zipline & Sloth Encounter", "price": 99, "duration_hrs": 4,
     "tags": ["thrill", "nature", "family"], "activity": "high"},
    {"id": "RTB-WESTBAY", "port": "RTB", "name": "West Bay Beach Break", "price": 59, "duration_hrs": 5,
     "tags": ["beach", "relaxation", "snorkeling"], "activity": "low"},
    # Costa Maya
    {"id": "CMY-CHACCHOBEN", "port": "CMY", "name": "Chacchoben Mayan Ruins", "price": 89, "duration_hrs": 5,
     "tags": ["history", "culture", "nature"], "activity": "medium"},
    {"id": "CMY-BACALAR", "port": "CMY", "name": "Bacalar Lagoon of Seven Colors Kayak", "price": 119, "duration_hrs": 6,
     "tags": ["kayaking", "nature", "photography"], "activity": "high"},
    # Nassau
    {"id": "NAS-ATLANTIS", "port": "NAS", "name": "Atlantis Aquaventure Water Park", "price": 199, "duration_hrs": 6,
     "tags": ["waterpark", "family", "thrill"], "activity": "high"},
    {"id": "NAS-PIGS", "port": "NAS", "name": "Swimming Pigs & Sandbar Speedboat", "price": 169, "duration_hrs": 4,
     "tags": ["ocean", "nature", "photography"], "activity": "medium"},
    {"id": "NAS-FOOD", "port": "NAS", "name": "Bahamian Food & Rum Walking Tour", "price": 79, "duration_hrs": 3,
     "tags": ["food", "culture"], "activity": "low"},
    # St. Thomas
    {"id": "STT-MAGENS", "port": "STT", "name": "Magens Bay Beach & Mountain Top", "price": 59, "duration_hrs": 4,
     "tags": ["beach", "views", "relaxation"], "activity": "low"},
    {"id": "STT-STJOHN", "port": "STT", "name": "St. John Snorkel Catamaran", "price": 129, "duration_hrs": 5,
     "tags": ["snorkeling", "ocean", "sailing"], "activity": "medium"},
    # St. Maarten
    {"id": "SXM-REGATTA", "port": "SXM", "name": "America's Cup 12-Metre Regatta", "price": 119, "duration_hrs": 3,
     "tags": ["sailing", "thrill", "adults"], "activity": "high"},
    {"id": "SXM-MAHO", "port": "SXM", "name": "Maho Beach & Marigot Shopping", "price": 49, "duration_hrs": 4,
     "tags": ["beach", "shopping", "photography"], "activity": "low"},
    # Labadee
    {"id": "LAB-DRAGON", "port": "LAB", "name": "Dragon's Breath Flight Line", "price": 109, "duration_hrs": 1,
     "tags": ["thrill", "views"], "activity": "high"},
    {"id": "LAB-CABANA", "port": "LAB", "name": "Private Beach Cabana", "price": 299, "duration_hrs": 6,
     "tags": ["beach", "luxury", "relaxation", "family"], "activity": "low"},
    # Falmouth
    {"id": "FAL-DUNNS", "port": "FAL", "name": "Dunn's River Falls Climb", "price": 99, "duration_hrs": 6,
     "tags": ["nature", "thrill", "family"], "activity": "high"},
    {"id": "FAL-BAMBOO", "port": "FAL", "name": "Martha Brae Bamboo Rafting", "price": 89, "duration_hrs": 4,
     "tags": ["nature", "relaxation", "culture"], "activity": "low"},
    # Ensenada / Catalina
    {"id": "ENS-WINE", "port": "ENS", "name": "Guadalupe Valley Wine Tasting", "price": 129, "duration_hrs": 7,
     "tags": ["wine", "food", "adults"], "activity": "low"},
    {"id": "ENS-BUFADORA", "port": "ENS", "name": "La Bufadora Blowhole & Market", "price": 59, "duration_hrs": 4,
     "tags": ["views", "shopping", "culture"], "activity": "low"},
    {"id": "CAT-ZIP", "port": "CAT", "name": "Catalina Zip Line Eco Tour", "price": 139, "duration_hrs": 2,
     "tags": ["thrill", "nature", "views"], "activity": "high"},
    {"id": "CAT-GLASS", "port": "CAT", "name": "Glass-Bottom Boat & Avalon Stroll", "price": 59, "duration_hrs": 2,
     "tags": ["ocean", "family", "relaxation"], "activity": "low"},
]
EXCURSION_BY_ID = {e["id"]: e for e in EXCURSIONS}

INTERESTS = sorted({t for e in EXCURSIONS for t in e["tags"]} | {"spa", "fitness", "casino", "live shows", "kids club"})

# --------------------------------------------------------------------------
# Specialty dining, packages, spa
# --------------------------------------------------------------------------
DINING = [
    {"id": "CHOPS", "name": "Chops Grille", "cuisine": "Steakhouse", "price_pp": 64, "ships": "*",
     "tags": ["steak", "celebration", "classic"]},
    {"id": "GIOVANNI", "name": "Giovanni's Italian Kitchen", "cuisine": "Italian", "price_pp": 45, "ships": "*",
     "tags": ["family", "italian", "wine"]},
    {"id": "IZUMI", "name": "Izumi Hibachi & Sushi", "cuisine": "Japanese", "price_pp": 49, "ships": "*",
     "tags": ["sushi", "family", "show"]},
    {"id": "HOOKED", "name": "Hooked Seafood", "cuisine": "Seafood", "price_pp": 52, "ships": ["ICN", "UT", "WN", "SY", "ST"],
     "tags": ["seafood", "views"]},
    {"id": "150CP", "name": "150 Central Park", "cuisine": "Chef's tasting", "price_pp": 75, "ships": ["UT", "WN", "SY", "HM", "AL"],
     "tags": ["fine dining", "celebration", "wine"]},
    {"id": "EMPIRE", "name": "Empire Supper Club", "cuisine": "Jazz-age tasting menu", "price_pp": 200, "ships": ["ICN", "ST"],
     "tags": ["fine dining", "celebration", "live music", "adults"]},
    {"id": "WONDERLAND", "name": "Wonderland Imaginative Cuisine", "cuisine": "Molecular", "price_pp": 65, "ships": ["SY", "HM", "WN", "UT"],
     "tags": ["creative", "celebration"]},
    {"id": "CHEFSTABLE", "name": "Chef's Table", "cuisine": "Five-course wine pairing", "price_pp": 135, "ships": "*",
     "tags": ["fine dining", "wine", "celebration", "adults"]},
]
DINING_BY_ID = {d["id"]: d for d in DINING}
DINING_TIMES = ["17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"]

PACKAGES = [
    {"code": "DELUXE_BEV", "name": "Deluxe Beverage Package", "price_per_day": 79, "per": "person/day",
     "blurb": "Cocktails, wine by the glass, beer, premium coffee, fresh juice and soda.", "propensity": "beverage_package_propensity"},
    {"code": "REFRESH", "name": "Refreshment Package", "price_per_day": 39, "per": "person/day",
     "blurb": "Premium coffee, mocktails, fresh juice and soda.", "propensity": "beverage_package_propensity"},
    {"code": "VOOM", "name": "VOOM Surf + Stream Internet", "price_per_day": 23, "per": "device/day",
     "blurb": "Fastest internet at sea - stream, video call and post from anywhere on board.", "propensity": "wifi_propensity"},
    {"code": "THE_KEY", "name": "The Key", "price_per_day": 45, "per": "person/day",
     "blurb": "Priority boarding, lunch at a specialty restaurant on embarkation day, reserved show seating and VOOM.",
     "propensity": "the_key_propensity"},
    {"code": "ULT_DINING", "name": "Ultimate Dining Package", "price_per_day": 55, "per": "person/day",
     "blurb": "Dinner at every specialty restaurant on board, every night.", "propensity": "specialty_dining_propensity"},
]
PACKAGE_BY_CODE = {p["code"]: p for p in PACKAGES}

SPA = [
    {"id": "SPA-HOTSTONE", "name": "Hot Stone Massage", "price": 199, "minutes": 75, "tags": ["relaxation", "spa"]},
    {"id": "SPA-COUPLES", "name": "Couples Massage", "price": 349, "minutes": 50, "tags": ["celebration", "spa", "couples"]},
    {"id": "SPA-FACIAL", "name": "Elemis Pro-Collagen Facial", "price": 179, "minutes": 50, "tags": ["spa", "beauty"]},
    {"id": "SPA-THERMAL", "name": "Thermal Suite Pass (sailing)", "price": 249, "minutes": 0, "tags": ["spa", "relaxation", "wellness"]},
    {"id": "SPA-ACUP", "name": "Medical Acupuncture", "price": 165, "minutes": 50, "tags": ["wellness"]},
]
SPA_BY_ID = {s["id"]: s for s in SPA}

ARRIVAL_SLOTS = ["10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00"]

LOYALTY_TIERS = ["Gold", "Platinum", "Emerald", "Diamond", "Diamond Plus", "Pinnacle Club"]
LOYALTY_THRESHOLDS = {"Gold": 0, "Platinum": 3, "Emerald": 55, "Diamond": 80, "Diamond Plus": 175, "Pinnacle Club": 700}


def ship_has_dining(ship_code: str, dining_id: str) -> bool:
    ships = DINING_BY_ID[dining_id]["ships"]
    return ships == "*" or ship_code in ships


def a_or_an(name: str) -> str:
    """'a Grand Suite', 'an Ocean View'."""
    return f"{'an' if name[:1].lower() in 'aeiou' else 'a'} {name}"


def dining_full(sailing_id: str, restaurant_id: str, date: str, time: str) -> bool:
    """Deterministic "fully booked" seatings (about 1 in 5) for a sailing -
    the restaurant reservation system's view of the night."""
    return _h(sailing_id, restaurant_id, date, time) % 5 == 0


def dining_availability(reservation: dict) -> dict:
    """Fully booked times per restaurant per night, for every specialty
    restaurant on the guest's ship: {restaurant_id: {date: [times]}}. Synced to
    the phone with the offers so the dining screen can grey out full seatings,
    offline too."""
    nights = [p["date"] for p in reservation["ports"]][:-1]
    out: dict = {}
    for d in DINING:
        if not ship_has_dining(reservation["ship_code"], d["id"]):
            continue
        out[d["id"]] = {n: [t for t in DINING_TIMES if dining_full(reservation["sailing_id"], d["id"], n, t)]
                        for n in nights}
    return out


def public_catalog() -> dict:
    """What the mobile app syncs as `catalog` documents."""
    return {
        "ships": SHIPS,
        "ports": PORTS,
        "itineraries": ITINERARIES,
        "cabin_categories": [
            {**{k: v for k, v in c.items() if k != "decks"}, "perks": CATEGORY_PERKS.get(c["code"], [])}
            for c in CABIN_CATEGORIES
        ],
        "excursions": EXCURSIONS,
        "dining": DINING,
        "dining_times": DINING_TIMES,
        "packages": PACKAGES,
        "spa": SPA,
        "arrival_slots": ARRIVAL_SLOTS,
    }
