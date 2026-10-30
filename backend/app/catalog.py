"""Reference catalog for the demo: ships, itineraries, stateroom categories,
shore excursions, specialty dining, packages and spa.

This is the single source of truth shared by the Databricks mock-dump
generator (databricks/generate_mock_dump.py imports it), the backend's
personalization engine and the MCP tools. Prices and names are illustrative
demo values, not live Princess Cruises pricing.
"""
from __future__ import annotations

import hashlib

# --------------------------------------------------------------------------
# Fleet. Princess ships have named decks rather than neighborhoods; the
# `neighborhoods` list is the deck names staterooms are assigned to.
# --------------------------------------------------------------------------
SHIPS = {
    "SUN": {"name": "Sun Princess", "class": "Sphere", "home_port": "FLL",
            "neighborhoods": ["Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera", "Marina"]},
    "STR": {"name": "Star Princess", "class": "Sphere", "home_port": "FLL",
            "neighborhoods": ["Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera", "Marina"]},
    "ENC": {"name": "Enchanted Princess", "class": "Royal", "home_port": "FLL",
            "neighborhoods": ["Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera", "Marina"]},
    "SKY": {"name": "Sky Princess", "class": "Royal", "home_port": "FLL",
            "neighborhoods": ["Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera", "Marina"]},
    "REG": {"name": "Regal Princess", "class": "Royal", "home_port": "GAL",
            "neighborhoods": ["Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera", "Marina"]},
    "CAR": {"name": "Caribbean Princess", "class": "Grand", "home_port": "FLL",
            "neighborhoods": ["Plaza", "Fiesta", "Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera"]},
    "DIS": {"name": "Discovery Princess", "class": "Royal", "home_port": "LAX",
            "neighborhoods": ["Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera", "Marina"]},
    "RUB": {"name": "Ruby Princess", "class": "Grand", "home_port": "LAX",
            "neighborhoods": ["Plaza", "Fiesta", "Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera"]},
}

PORTS = {
    "FLL": "Fort Lauderdale (Port Everglades), Florida",
    "GAL": "Galveston, Texas",
    "LAX": "Los Angeles (San Pedro), California",
    "PCY": "Princess Cays, Eleuthera, Bahamas",
    "NAS": "Nassau, Bahamas",
    "CZM": "Cozumel, Mexico",
    "RTB": "Roatán, Honduras",
    "CMY": "Costa Maya, Mexico",
    "STT": "Charlotte Amalie, St. Thomas",
    "SXM": "Philipsburg, St. Maarten",
    "GCM": "George Town, Grand Cayman",
    "FAL": "Falmouth, Jamaica",
    "CAB": "Cabo San Lucas, Mexico",
    "MZT": "Mazatlán, Mexico",
    "PVR": "Puerto Vallarta, Mexico",
    "ENS": "Ensenada, Mexico",
    "SAN": "San Diego, California",
    "SEA": "At sea",
}

# itinerary_code -> definition. `days` lists one entry per day of the sailing.
ITINERARIES = {
    "7WCPC": {"name": "7 Night Western Caribbean with Princess Cays", "nights": 7,
              "days": ["EMB", "SEA", "RTB", "CMY", "CZM", "SEA", "PCY", "DEB"]},
    "7ECPC": {"name": "7 Night Eastern Caribbean with Princess Cays", "nights": 7,
              "days": ["EMB", "SEA", "STT", "SXM", "SEA", "SEA", "PCY", "DEB"]},
    "4BAPC": {"name": "4 Night Bahamas & Princess Cays", "nights": 4,
              "days": ["EMB", "NAS", "PCY", "SEA", "DEB"]},
    "3BAPC": {"name": "3 Night Bahamas Getaway with Princess Cays", "nights": 3,
              "days": ["EMB", "PCY", "NAS", "DEB"]},
    "7WCGC": {"name": "7 Night Western Caribbean with Grand Cayman & Falmouth", "nights": 7,
              "days": ["EMB", "SEA", "GCM", "FAL", "SEA", "CZM", "SEA", "DEB"]},
    "7MXRV": {"name": "7 Night Mexican Riviera", "nights": 7,
              "days": ["EMB", "SEA", "SEA", "CAB", "MZT", "PVR", "SEA", "DEB"]},
    "4CAGW": {"name": "4 Night California Coast Getaway", "nights": 4,
              "days": ["EMB", "SAN", "ENS", "SEA", "DEB"]},
}

# ship -> itineraries it sails (first is the "anchor" itinerary)
SHIP_ITINERARIES = {
    "SUN": ["7ECPC", "7WCPC"],
    "STR": ["7WCPC", "7ECPC"],
    "ENC": ["7ECPC", "7WCPC"],
    "SKY": ["4BAPC", "7ECPC"],
    "REG": ["7WCGC"],
    "CAR": ["3BAPC", "4BAPC"],
    "DIS": ["7MXRV", "4CAGW"],
    "RUB": ["4CAGW", "7MXRV"],
}

# --------------------------------------------------------------------------
# Staterooms. Rank is the upgrade ladder; prices are per person per night.
# --------------------------------------------------------------------------
CABIN_CATEGORIES = [
    {"code": "IN", "name": "Interior", "rank": 1, "base_ppn": 115, "decks": (5, 12)},
    {"code": "OV", "name": "Oceanview", "rank": 2, "base_ppn": 140, "decks": (5, 12)},
    {"code": "BA", "name": "Balcony", "rank": 3, "base_ppn": 185, "decks": (8, 15)},
    {"code": "MS", "name": "Mini-Suite", "rank": 4, "base_ppn": 290, "decks": (8, 15)},
    {"code": "PS", "name": "Premium Suite", "rank": 5, "base_ppn": 470, "decks": (9, 16)},
    {"code": "OS", "name": "Owner's Suite", "rank": 6, "base_ppn": 690, "decks": (9, 16)},
    {"code": "SK", "name": "Sky Suite", "rank": 7, "base_ppn": 1150, "decks": (17, 18)},
]
CATEGORY_BY_CODE = {c["code"]: c for c in CABIN_CATEGORIES}
CATEGORY_PERKS = {
    "BA": ["Private balcony", "Sitting area"],
    "MS": ["Separate sitting area with sofa bed", "Two flat-panel TVs", "Premium bathroom amenities", "Welcome sparkling wine"],
    "PS": ["Suite Collection perks", "Reserve Collection dining", "Priority embarkation & disembarkation", "Specialty dining on embarkation night"],
    "OS": ["Separate living & dining room", "Suite concierge", "Specialty dining included", "Lotus Spa thermal suite access"],
    "SK": ["Largest balcony at sea", "Sleeps up to five", "Dedicated suite host", "Unlimited beverages & specialty dining"],
}

# Minimum Princess Upgrade bid per person per night for a step of N ranks.
UPGRADE_BID_MIN_PPN = {1: 25, 2: 60, 3: 110, 4: 220, 5: 380}


def upgrade_price_ppn(from_code: str, to_code: str) -> int:
    """Instant-upgrade price (per person per night) between two categories."""
    a, b = CATEGORY_BY_CODE[from_code], CATEGORY_BY_CODE[to_code]
    delta = max(0, b["base_ppn"] - a["base_ppn"])
    # Last-minute upgrade discount, but always comfortably above the bid
    # floor - otherwise bidding would never make sense.
    price = max(delta * 0.82, upgrade_bid_min(from_code, to_code) * 1.6)
    return int(round(price / 5.0) * 5)


def upgrade_bid_min(from_code: str, to_code: str) -> int:
    steps = CATEGORY_BY_CODE[to_code]["rank"] - CATEGORY_BY_CODE[from_code]["rank"]
    return UPGRADE_BID_MIN_PPN.get(steps, 0)


def _h(*parts: str) -> int:
    return int(hashlib.sha1("|".join(parts).encode()).hexdigest()[:8], 16)


def initial_inventory(sailing_id: str) -> dict:
    """Deterministic unsold staterooms per category for a sailing - what the
    revenue team would release to upgrades a week or two before sailing."""
    out = {}
    for c in CABIN_CATEGORIES:
        if c["code"] == "IN":
            continue
        cap = {"OV": 14, "BA": 22, "MS": 9, "PS": 4, "OS": 2, "SK": 1}[c["code"]]
        out[c["code"]] = _h(sailing_id, c["code"]) % (cap + 1)
    # Always leave a little room in the hero categories so demos never dead-end.
    out["BA"] = max(out["BA"], 3)
    out["MS"] = max(out["MS"], 2)
    out["PS"] = max(out["PS"], 1)
    return out


# --------------------------------------------------------------------------
# Shore excursions (tags drive interest matching)
# --------------------------------------------------------------------------
EXCURSIONS = [
    # Princess Cays
    {"id": "PCY-BUNGALOW", "port": "PCY", "name": "Private Beach Bungalow", "price": 249, "duration_hrs": 6,
     "tags": ["beach", "luxury", "relaxation", "family"], "activity": "low"},
    {"id": "PCY-CLAMSHELL", "port": "PCY", "name": "Clamshell & Float Beach Package", "price": 49, "duration_hrs": 6,
     "tags": ["beach", "relaxation", "adults"], "activity": "low"},
    {"id": "PCY-SNORKEL", "port": "PCY", "name": "Princess Cays Reef Snorkel", "price": 69, "duration_hrs": 2,
     "tags": ["snorkeling", "ocean", "nature"], "activity": "medium"},
    {"id": "PCY-AQUAPARK", "port": "PCY", "name": "Floating Aqua Park & Banana Boat", "price": 59, "duration_hrs": 3,
     "tags": ["waterpark", "family", "thrill"], "activity": "high"},
    {"id": "PCY-KAYAK", "port": "PCY", "name": "Glass-Bottom Kayak Eco Tour", "price": 79, "duration_hrs": 2,
     "tags": ["kayaking", "nature", "photography"], "activity": "medium"},
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
    # Grand Cayman
    {"id": "GCM-STINGRAY", "port": "GCM", "name": "Stingray City Sandbar & Snorkel", "price": 89, "duration_hrs": 4,
     "tags": ["ocean", "nature", "snorkeling", "family"], "activity": "medium"},
    {"id": "GCM-SEVENMILE", "port": "GCM", "name": "Seven Mile Beach Club Day", "price": 79, "duration_hrs": 5,
     "tags": ["beach", "relaxation", "luxury"], "activity": "low"},
    # Falmouth
    {"id": "FAL-DUNNS", "port": "FAL", "name": "Dunn's River Falls Climb", "price": 99, "duration_hrs": 6,
     "tags": ["nature", "thrill", "family"], "activity": "high"},
    {"id": "FAL-BAMBOO", "port": "FAL", "name": "Martha Brae Bamboo Rafting", "price": 89, "duration_hrs": 4,
     "tags": ["nature", "relaxation", "culture"], "activity": "low"},
    # Mexican Riviera
    {"id": "CAB-ARCH", "port": "CAB", "name": "The Arch & Lover's Beach by Glass-Bottom Boat", "price": 59, "duration_hrs": 2,
     "tags": ["ocean", "views", "photography", "family"], "activity": "low"},
    {"id": "CAB-SNORKEL", "port": "CAB", "name": "Santa Maria Bay Snorkel Sail", "price": 109, "duration_hrs": 4,
     "tags": ["snorkeling", "sailing", "ocean"], "activity": "medium"},
    {"id": "MZT-OLDTOWN", "port": "MZT", "name": "Old Mazatlán & Cliff Divers", "price": 69, "duration_hrs": 4,
     "tags": ["history", "culture", "views"], "activity": "low"},
    {"id": "PVR-ZIP", "port": "PVR", "name": "Sierra Madre Zipline & Tequila Tasting", "price": 129, "duration_hrs": 5,
     "tags": ["thrill", "nature", "adults"], "activity": "high"},
    {"id": "PVR-WHALE", "port": "PVR", "name": "Banderas Bay Whale & Dolphin Watch", "price": 99, "duration_hrs": 3,
     "tags": ["ocean", "nature", "photography", "family"], "activity": "low"},
    # Ensenada / San Diego
    {"id": "ENS-WINE", "port": "ENS", "name": "Guadalupe Valley Wine Tasting", "price": 129, "duration_hrs": 7,
     "tags": ["wine", "food", "adults"], "activity": "low"},
    {"id": "ENS-BUFADORA", "port": "ENS", "name": "La Bufadora Blowhole & Market", "price": 59, "duration_hrs": 4,
     "tags": ["views", "shopping", "culture"], "activity": "low"},
    {"id": "SAN-MIDWAY", "port": "SAN", "name": "USS Midway Museum & Harbor Cruise", "price": 89, "duration_hrs": 4,
     "tags": ["history", "family", "views"], "activity": "low"},
    {"id": "SAN-LAJOLLA", "port": "SAN", "name": "La Jolla Sea Cave Kayak", "price": 99, "duration_hrs": 3,
     "tags": ["kayaking", "ocean", "nature", "thrill"], "activity": "high"},
]
EXCURSION_BY_ID = {e["id"]: e for e in EXCURSIONS}

INTERESTS = sorted({t for e in EXCURSIONS for t in e["tags"]} | {"spa", "fitness", "casino", "live shows", "kids club"})

# --------------------------------------------------------------------------
# Specialty dining, packages, spa
# --------------------------------------------------------------------------
DINING = [
    {"id": "CROWNGRILL", "name": "Crown Grill", "cuisine": "Steakhouse", "price_pp": 49, "ships": "*",
     "tags": ["steak", "celebration", "classic"]},
    {"id": "SABATINIS", "name": "Sabatini's Italian Trattoria", "cuisine": "Italian", "price_pp": 45, "ships": "*",
     "tags": ["family", "italian", "wine"]},
    {"id": "KAISUSHI", "name": "Kai Sushi", "cuisine": "Japanese", "price_pp": 39, "ships": ["ENC", "SKY", "DIS", "REG"],
     "tags": ["sushi", "family", "show"]},
    {"id": "UMAI", "name": "Umai Teppanyaki", "cuisine": "Japanese teppanyaki", "price_pp": 49, "ships": ["SUN", "STR"],
     "tags": ["sushi", "family", "show"]},
    {"id": "THECATCH", "name": "The Catch by Rudi", "cuisine": "Seafood", "price_pp": 52, "ships": ["ENC", "SKY", "DIS", "CAR", "RUB"],
     "tags": ["seafood", "views"]},
    {"id": "BISTROSLM", "name": "Bistro Sur La Mer", "cuisine": "French bistro", "price_pp": 45, "ships": ["ENC", "SKY", "DIS", "REG"],
     "tags": ["fine dining", "celebration", "wine"]},
    {"id": "LOVEBRITTO", "name": "Love by Britto", "cuisine": "Romantic tasting menu", "price_pp": 200, "ships": ["SUN", "STR"],
     "tags": ["fine dining", "celebration", "live music", "adults"]},
    {"id": "BUTCHERS", "name": "Butcher's Block by Dario", "cuisine": "Tuscan steak feast", "price_pp": 65, "ships": ["SUN", "STR"],
     "tags": ["steak", "creative", "celebration"]},
    {"id": "CHEFSTABLE", "name": "Chef's Table", "cuisine": "Multi-course wine pairing", "price_pp": 135, "ships": "*",
     "tags": ["fine dining", "wine", "celebration", "adults"]},
]
DINING_BY_ID = {d["id"]: d for d in DINING}
DINING_TIMES = ["17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"]

PACKAGES = [
    {"code": "PLUS", "name": "Princess Plus", "price_per_day": 60, "per": "person/day",
     "blurb": "Plus Beverage Package (drinks up to $15), MedallionNet Wi-Fi for one device, crew appreciation, "
              "two casual-dining meals and OceanNow delivery.", "propensity": "beverage_package_propensity"},
    {"code": "ZERO_ALC", "name": "Zero-Alcohol Package", "price_per_day": 30, "per": "person/day",
     "blurb": "Premium coffee, mocktails, fresh juice, smoothies and soda.", "propensity": "beverage_package_propensity"},
    {"code": "MEDALLIONNET", "name": "MedallionNet Max Wi-Fi", "price_per_day": 25, "per": "device/day",
     "blurb": "The best Wi-Fi at sea - stream, video call and post from anywhere on board.", "propensity": "wifi_propensity"},
    {"code": "PREMIER", "name": "Princess Premier", "price_per_day": 90, "per": "person/day",
     "blurb": "Premier Beverage Package (drinks up to $20), MedallionNet for four devices, unlimited specialty dining, "
              "reserved theater seats, unlimited casual dining and digital photos.",
     "propensity": "premier_propensity"},
    {"code": "SPEC_DINING", "name": "Specialty Dining Package", "price_per_day": 55, "per": "person/day",
     "blurb": "Dinner at a specialty restaurant on board, every night of your voyage.", "propensity": "specialty_dining_propensity"},
]
PACKAGE_BY_CODE = {p["code"]: p for p in PACKAGES}

SPA = [
    {"id": "SPA-HOTSTONE", "name": "Lotus Spa Hot Stone Massage", "price": 199, "minutes": 75, "tags": ["relaxation", "spa"]},
    {"id": "SPA-COUPLES", "name": "Couples Massage", "price": 349, "minutes": 50, "tags": ["celebration", "spa", "couples"]},
    {"id": "SPA-FACIAL", "name": "Elemis Pro-Collagen Facial", "price": 179, "minutes": 50, "tags": ["spa", "beauty"]},
    {"id": "SPA-ENCLAVE", "name": "The Enclave Thermal Suite Pass (voyage)", "price": 249, "minutes": 0, "tags": ["spa", "relaxation", "wellness"]},
    {"id": "SPA-ACUP", "name": "Medical Acupuncture", "price": 165, "minutes": 50, "tags": ["wellness"]},
]
SPA_BY_ID = {s["id"]: s for s in SPA}

ARRIVAL_SLOTS = ["10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00"]

# Captain's Circle tiers. Thresholds are in loyalty points (the generator awards
# about 9 per completed cruise): Gold after the first cruise, Ruby from 3,
# Platinum from 5, Elite from 15.
LOYALTY_TIERS = ["Blue", "Gold", "Ruby", "Platinum", "Elite"]
LOYALTY_THRESHOLDS = {"Blue": 0, "Gold": 1, "Ruby": 27, "Platinum": 45, "Elite": 135}


def ship_has_dining(ship_code: str, dining_id: str) -> bool:
    ships = DINING_BY_ID[dining_id]["ships"]
    return ships == "*" or ship_code in ships


def a_or_an(name: str) -> str:
    """'a Premium Suite', 'an Oceanview'."""
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
