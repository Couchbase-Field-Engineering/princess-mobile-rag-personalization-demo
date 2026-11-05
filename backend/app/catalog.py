"""Reference catalog for the demo: ships, itineraries, stateroom categories,
shore excursions, specialty dining, packages and spa.

This is the single source of truth shared by the mock Real-Time CDP export
generator (adobe/generate_mock_export.py imports it), the backend's
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
    "MAJ": {"name": "Majestic Princess", "class": "Royal", "home_port": "GAL",
            "neighborhoods": ["Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera", "Marina"]},
    "ROY": {"name": "Royal Princess", "class": "Royal", "home_port": "SYD",
            "neighborhoods": ["Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera", "Marina"]},
    "GRA": {"name": "Grand Princess", "class": "Grand", "home_port": "SYD",
            "neighborhoods": ["Plaza", "Fiesta", "Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera"]},
    "CRO": {"name": "Crown Princess", "class": "Grand", "home_port": "LAX",
            "neighborhoods": ["Plaza", "Fiesta", "Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera"]},
    "EME": {"name": "Emerald Princess", "class": "Grand", "home_port": "FLL",
            "neighborhoods": ["Plaza", "Fiesta", "Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera"]},
    "DIA": {"name": "Diamond Princess", "class": "Grand", "home_port": "TYO",
            "neighborhoods": ["Plaza", "Fiesta", "Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera"]},
    "SAP": {"name": "Sapphire Princess", "class": "Grand", "home_port": "SIN",
            "neighborhoods": ["Plaza", "Fiesta", "Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Riviera"]},
    "COR": {"name": "Coral Princess", "class": "Coral", "home_port": "FLL",
            "neighborhoods": ["Plaza", "Fiesta", "Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Sun"]},
    "ISL": {"name": "Island Princess", "class": "Coral", "home_port": "FLL",
            "neighborhoods": ["Plaza", "Fiesta", "Emerald", "Dolphin", "Caribe", "Baja", "Aloha", "Sun"]},
}
FLEET_SIZE = len(SHIPS)  # the 17-ship Princess fleet

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
    # Australia & Tasmania
    "SYD": "Sydney (White Bay / Circular Quay), Australia",
    "ABH": "Airlie Beach (Whitsundays), Queensland",
    "CNS": "Cairns (Yorkeys Knob), Queensland",
    "BNE": "Brisbane, Queensland",
    "MEL": "Melbourne, Victoria",
    "HBA": "Hobart, Tasmania",
    "PTA": "Port Arthur, Tasmania",
    # Japan & Korea
    "TYO": "Tokyo (Yokohama), Japan",
    "KGS": "Kagoshima, Japan",
    "NGS": "Nagasaki, Japan",
    "BUS": "Busan, South Korea",
    # Southeast Asia
    "SIN": "Singapore (Marina Bay Cruise Centre)",
    "KUL": "Kuala Lumpur (Port Klang), Malaysia",
    "PEN": "Penang (George Town), Malaysia",
    "PKT": "Phuket, Thailand",
    # Panama Canal & Southern Caribbean
    "ARU": "Oranjestad, Aruba",
    "CTG": "Cartagena, Colombia",
    "PCN": "Panama Canal (Gatun Lake), Panama",
    "LIM": "Puerto Limón, Costa Rica",
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
    "7QLDR": {"name": "7 Night Queensland & Great Barrier Reef", "nights": 7,
              "days": ["EMB", "SEA", "BNE", "ABH", "CNS", "SEA", "SEA", "DEB"]},
    "7TASM": {"name": "7 Night Tasmania & Melbourne", "nights": 7,
              "days": ["EMB", "SEA", "MEL", "SEA", "HBA", "PTA", "SEA", "DEB"]},
    "7JPKR": {"name": "7 Night Southern Japan & Korea", "nights": 7,
              "days": ["EMB", "SEA", "KGS", "NGS", "BUS", "SEA", "SEA", "DEB"]},
    "7SEAS": {"name": "7 Night Southeast Asia", "nights": 7,
              "days": ["EMB", "SEA", "PKT", "PEN", "KUL", "SEA", "SEA", "DEB"]},
    "10PCN": {"name": "10 Night Panama Canal with Costa Rica & Caribbean", "nights": 10,
              "days": ["EMB", "SEA", "SEA", "ARU", "CTG", "PCN", "LIM", "SEA", "GCM", "SEA", "DEB"]},
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
    "MAJ": ["7WCGC"],
    "ROY": ["7QLDR"],
    "GRA": ["7TASM", "7QLDR"],
    "CRO": ["7MXRV", "4CAGW"],
    "EME": ["7WCPC", "7ECPC"],
    "DIA": ["7JPKR"],
    "SAP": ["7SEAS"],
    "COR": ["10PCN", "7ECPC"],
    "ISL": ["10PCN", "7WCGC"],
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
    # Queensland
    {"id": "BNE-KOALA", "port": "BNE", "name": "Lone Pine Koala Sanctuary & River Cruise", "price": 89, "duration_hrs": 5,
     "tags": ["nature", "family", "photography"], "activity": "low"},
    {"id": "BNE-FOOD", "port": "BNE", "name": "Brisbane Laneways Food & Craft Beer Walk", "price": 79, "duration_hrs": 3,
     "tags": ["food", "culture", "adults"], "activity": "low"},
    {"id": "ABH-WHITEHAVEN", "port": "ABH", "name": "Whitehaven Beach & Hill Inlet Lookout", "price": 149, "duration_hrs": 6,
     "tags": ["beach", "views", "photography", "relaxation"], "activity": "medium"},
    {"id": "ABH-REEF", "port": "ABH", "name": "Great Barrier Reef Pontoon Snorkel", "price": 219, "duration_hrs": 8,
     "tags": ["snorkeling", "ocean", "nature"], "activity": "medium"},
    {"id": "CNS-KURANDA", "port": "CNS", "name": "Kuranda Skyrail & Scenic Railway", "price": 139, "duration_hrs": 7,
     "tags": ["nature", "views", "family", "culture"], "activity": "low"},
    {"id": "CNS-DAINTREE", "port": "CNS", "name": "Daintree Rainforest & Mossman Gorge", "price": 159, "duration_hrs": 8,
     "tags": ["nature", "photography", "culture"], "activity": "medium"},
    # Tasmania & Melbourne
    {"id": "MEL-PENGUIN", "port": "MEL", "name": "Phillip Island Penguin Parade", "price": 129, "duration_hrs": 8,
     "tags": ["nature", "family", "photography"], "activity": "low"},
    {"id": "MEL-YARRA", "port": "MEL", "name": "Yarra Valley Wine & Cheese Trail", "price": 149, "duration_hrs": 7,
     "tags": ["wine", "food", "adults"], "activity": "low"},
    {"id": "HBA-MONA", "port": "HBA", "name": "MONA Museum by Ferry", "price": 89, "duration_hrs": 4,
     "tags": ["culture", "adults", "views"], "activity": "low"},
    {"id": "HBA-WELLINGTON", "port": "HBA", "name": "Mt Wellington Summit & Bonorong Wildlife", "price": 109, "duration_hrs": 5,
     "tags": ["nature", "views", "family"], "activity": "medium"},
    {"id": "PTA-HISTORIC", "port": "PTA", "name": "Port Arthur Historic Site & Harbour Cruise", "price": 79, "duration_hrs": 4,
     "tags": ["history", "culture", "views"], "activity": "low"},
    {"id": "PTA-TASMAN", "port": "PTA", "name": "Tasman Peninsula Sea Cliffs Eco-Cruise", "price": 139, "duration_hrs": 3,
     "tags": ["ocean", "nature", "thrill", "photography"], "activity": "high"},
    # Japan & Korea
    {"id": "KGS-SAKURAJIMA", "port": "KGS", "name": "Sakurajima Volcano & Sengan-en Garden", "price": 119, "duration_hrs": 6,
     "tags": ["nature", "views", "culture", "photography"], "activity": "medium"},
    {"id": "KGS-SHOCHU", "port": "KGS", "name": "Kurobuta Lunch & Shochu Distillery", "price": 99, "duration_hrs": 4,
     "tags": ["food", "culture", "adults"], "activity": "low"},
    {"id": "NGS-PEACE", "port": "NGS", "name": "Peace Park & Glover Garden", "price": 79, "duration_hrs": 4,
     "tags": ["history", "culture", "views"], "activity": "low"},
    {"id": "NGS-GUNKANJIMA", "port": "NGS", "name": "Gunkanjima (Battleship Island) Cruise", "price": 109, "duration_hrs": 4,
     "tags": ["history", "ocean", "photography"], "activity": "medium"},
    {"id": "BUS-GAMCHEON", "port": "BUS", "name": "Gamcheon Culture Village & Haedong Temple", "price": 89, "duration_hrs": 5,
     "tags": ["culture", "photography", "views"], "activity": "medium"},
    {"id": "BUS-MARKET", "port": "BUS", "name": "Jagalchi Fish Market & Korean Street Food", "price": 69, "duration_hrs": 3,
     "tags": ["food", "culture", "shopping"], "activity": "low"},
    # Southeast Asia
    {"id": "PKT-PHIPHI", "port": "PKT", "name": "Phi Phi Islands Speedboat & Snorkel", "price": 149, "duration_hrs": 7,
     "tags": ["snorkeling", "beach", "ocean", "thrill"], "activity": "high"},
    {"id": "PKT-ELEPHANT", "port": "PKT", "name": "Ethical Elephant Sanctuary Visit", "price": 129, "duration_hrs": 4,
     "tags": ["nature", "family", "photography"], "activity": "low"},
    {"id": "PEN-HERITAGE", "port": "PEN", "name": "George Town Heritage Trishaw & Street Art", "price": 69, "duration_hrs": 4,
     "tags": ["culture", "history", "photography"], "activity": "low"},
    {"id": "PEN-FOOD", "port": "PEN", "name": "Penang Hawker Food Crawl", "price": 59, "duration_hrs": 3,
     "tags": ["food", "culture"], "activity": "low"},
    {"id": "KUL-TOWERS", "port": "KUL", "name": "Kuala Lumpur Highlights & Petronas Towers", "price": 109, "duration_hrs": 8,
     "tags": ["views", "culture", "shopping", "photography"], "activity": "medium"},
    {"id": "KUL-BATU", "port": "KUL", "name": "Batu Caves & Royal Selangor Pewter", "price": 89, "duration_hrs": 6,
     "tags": ["culture", "history", "nature"], "activity": "medium"},
    # Panama Canal & Southern Caribbean
    {"id": "ARU-SUBMARINE", "port": "ARU", "name": "Atlantis Submarine Reef Dive", "price": 129, "duration_hrs": 2,
     "tags": ["ocean", "nature", "family"], "activity": "low"},
    {"id": "ARU-JEEP", "port": "ARU", "name": "Natural Pool 4x4 Safari", "price": 109, "duration_hrs": 5,
     "tags": ["thrill", "nature", "beach"], "activity": "high"},
    {"id": "CTG-WALLED", "port": "CTG", "name": "Walled City & Castillo San Felipe", "price": 69, "duration_hrs": 4,
     "tags": ["history", "culture", "photography"], "activity": "low"},
    {"id": "CTG-ROSARIO", "port": "CTG", "name": "Rosario Islands Beach Escape", "price": 139, "duration_hrs": 6,
     "tags": ["beach", "snorkeling", "relaxation"], "activity": "low"},
    {"id": "PCN-LOCKS", "port": "PCN", "name": "Agua Clara Locks & Gatun Lake Boat Tour", "price": 119, "duration_hrs": 5,
     "tags": ["history", "views", "family", "photography"], "activity": "low"},
    {"id": "PCN-RAINFOREST", "port": "PCN", "name": "Gatun Rainforest Aerial Tram & Sloth Sanctuary", "price": 139, "duration_hrs": 6,
     "tags": ["nature", "family", "photography"], "activity": "medium"},
    {"id": "LIM-TORTUGUERO", "port": "LIM", "name": "Tortuguero Canals Wildlife Boat", "price": 99, "duration_hrs": 5,
     "tags": ["nature", "photography", "family"], "activity": "low"},
    {"id": "LIM-ZIPLINE", "port": "LIM", "name": "Veragua Rainforest Zipline & Hanging Bridges", "price": 129, "duration_hrs": 6,
     "tags": ["thrill", "nature", "adults"], "activity": "high"},
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
    {"id": "KAISUSHI", "name": "Kai Sushi", "cuisine": "Japanese", "price_pp": 39, "ships": ["ENC", "SKY", "DIS", "REG", "ROY", "MAJ"],
     "tags": ["sushi", "family", "show"]},
    {"id": "UMAI", "name": "Umai Teppanyaki", "cuisine": "Japanese teppanyaki", "price_pp": 49, "ships": ["SUN", "STR"],
     "tags": ["sushi", "family", "show"]},
    {"id": "THECATCH", "name": "The Catch by Rudi", "cuisine": "Seafood", "price_pp": 52, "ships": ["ENC", "SKY", "DIS", "CAR", "RUB", "CRO", "EME", "GRA", "DIA", "SAP", "COR", "ISL"],
     "tags": ["seafood", "views"]},
    {"id": "BISTROSLM", "name": "Bistro Sur La Mer", "cuisine": "French bistro", "price_pp": 45, "ships": ["ENC", "SKY", "DIS", "REG", "ROY", "MAJ"],
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
