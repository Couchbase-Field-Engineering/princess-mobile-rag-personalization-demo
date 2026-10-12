"""RCI Guest Concierge - the agent behind the app's Concierge tab.

One turn:

1. **Classify** the question into an intent, and decide whether it is
   *personal* (needs this guest's data) or a *playbook* question anyone
   could ask ("what's in The Key?").
2. **Playbook questions -> AOM RAG Application.** One call to
   `/v1/agent/rag/rci-guest-concierge/query`. The app is scoped to today's
   Guest Services Playbook document; AOM runs retrieval behind its Context
   Cache and generation behind its LLM Cache, and counts the query on its
   RAG Applications page. If the app isn't registered (or AOM predates RAG
   Applications) the question takes the personal path below without guest
   data.
3. **Personal questions -> Context Caching.** Look the context up in AOM's
   Context Cache (`/v1/context/get`, namespace
   `rag:rci-guest-concierge:guest-context`), then in the Couchbase
   `ctx::<guest>::<intent>` document. On a miss, assemble it: AOM Knowledge
   Base retrieval scoped to this guest's profile document and to the
   playbook, plus live facts from the governed MCP tools (upgrade
   inventory, excursions at their ports). It is stored in AOM
   (`/v1/context/set`, with the real build time) and in Couchbase, keyed by
   the dump date and the profile revision, so the next daily load or any
   booking the guest makes invalidates it. The Couchbase copy carries the
   guest's channel, so Sync Gateway puts it on the phone too - which is what
   lets the app answer offline.
4. **Memory** - recall what this guest told the concierge before (AOM agent
   memory), live every turn.
5. **LLM Caching** - complete through AOM `/v1/llm/complete` in the
   `rag:rci-guest-concierge:personal` namespace (the `rag:<app>:` prefix is
   how AOM attributes the activity to the RAG application).
6. Suggest one-tap actions; the app turns a tap into an offline-first
   `requests` document.
"""
from __future__ import annotations

import logging
import re
import time
import uuid

from . import catalog as C
from . import config, knowledge, rag_app, tool_gateway
from .aom_client import AOMError, aom, current_trace
from .docs import (STATE, chat_id, ctx_id, days_to_sail, guest_channel, now_iso,
                   profile_id)
from .store import store

log = logging.getLogger("rccl.concierge")

INTENTS = ["upgrade", "excursion", "dining", "package", "spa", "checkin", "itinerary", "service_recovery", "general"]
# Context-cache keys: personal context per intent, plus a playbook-only
# context per intent for generic questions (no guest data in it).
CONTEXT_KEYS = INTENTS + [f"playbook_{i}" for i in INTENTS]

KEYWORDS = {
    "service_recovery": ["noisy", "noise", "broken", "dirty", "complain", "disappointed", "upset", "terrible", "awful",
                         "not working", "problem with my room", "problem with our room", "leak", "smell"],
    "upgrade": ["upgrade", "suite", "royalup", "royal up", "bid", "balcony", "bigger room", "bigger cabin", "stateroom",
                "cabin", "ocean view", "loft"],
    "excursion": ["excursion", "shore", "snorkel", "tour", "cococay", "beach", "things to do", "port", "zipline",
                  "ruins", "waterpark", "kids do"],
    "dining": ["dinner", "dining", "restaurant", "eat", "chops", "steak", "sushi", "italian", "chef's table", "table for",
               "anniversary dinner"],
    "package": ["drink", "beverage", "wifi", "wi-fi", "internet", "voom", "the key", "package", "cocktail", "soda"],
    "spa": ["spa", "massage", "facial", "relax", "thermal", "wellness"],
    "checkin": ["check-in", "check in", "checkin", "arrival time", "boarding", "setsail", "set sail", "documents", "terminal"],
    "itinerary": ["itinerary", "schedule", "what day", "which day", "when do we", "ports", "port times", "sea day", "my trip",
                  "my cruise", "where are we"],
}
PERSONAL_RE = re.compile(r"\b(i|i'm|im|me|my|mine|we|we're|our|us)\b", re.I)
PERSONAL_INTENTS = {"upgrade", "itinerary", "service_recovery"}

# Canonical retrieval query per intent: the cached context is per intent, so
# it is retrieved with a stable query rather than the wording of whichever
# question happened to miss the cache first.
INTENT_QUERY = {
    "upgrade": "stateroom category upgrade RoyalUp bid suite perks",
    "excursion": "shore excursions ports itinerary interests",
    "dining": "specialty dining restaurants celebration dietary",
    "package": "beverage package internet VOOM The Key dining package",
    "spa": "Vitality Spa treatments massage port day",
    "checkin": "online check-in arrival time SetSail Pass documents",
    "itinerary": "itinerary ports days sailing schedule",
    "service_recovery": "stateroom issue service recovery goodwill upgrade",
    "general": "frequently asked questions policy",
}

PERSONA = ("You are the Royal Caribbean Guest Concierge in the guest's mobile app. Be warm, concise (under 120 words) "
           "and specific. Use only the facts in CONTEXT. Never invent prices, availability or bookings. Never say a "
           "booking is done - the guest confirms actions with the buttons shown under your reply.")


def classify(message: str) -> tuple[str, bool]:
    m = message.lower()
    scores = {i: sum(1 for k in kws if k in m) for i, kws in KEYWORDS.items()}
    intent = max(scores, key=scores.get)
    if scores[intent] == 0:
        intent = "general"
    personal = bool(PERSONAL_RE.search(message)) or intent in PERSONAL_INTENTS
    if intent == "general" and not personal:
        return "general", False
    # A product/policy question phrased generically ("how does RoyalUp work?")
    # stays on the shared playbook path even though its intent is personal-capable.
    if not PERSONAL_RE.search(message) and re.match(r"\s*(how|what|is|are|can|do|does|who)\b", m) and intent not in ("service_recovery",):
        return intent, False
    return intent, True


def _norm(q: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", q.lower()).strip()


async def kb_doc_id(key: str) -> str | None:
    doc = await store.get("lookups", f"kbdoc::{key}")
    return doc.get("document_id") if doc else None


# --------------------------------------------------------------------------
# Context cache
# --------------------------------------------------------------------------
async def invalidate_context(guest_id: str):
    for key in CONTEXT_KEYS:
        await store.remove("context_cache", ctx_id(guest_id, key))


async def _kb(query: str, document_id: str | None, top_k=3) -> tuple[list[dict], str]:
    if not (aom.enabled and document_id):
        return [], "unavailable"
    try:
        res = await aom.knowledge_search(query, top_k=top_k, document_id=document_id)
        return [{"title": r.get("document_title"), "content": r.get("content"), "score": round(r.get("score") or 0, 3),
                 "document_id": r.get("document_id"), "source": "aom-kb"} for r in res.get("results", [])], "aom"
    except AOMError as exc:
        log.warning("KB search failed: %s", exc)
        return [], "error"


def _local_profile_chunks(profile: dict, intent: str) -> list[dict]:
    md = knowledge.guest_profile_markdown(profile)
    sections = md.split("\n## ")
    want = {"upgrade": ["Upcoming", "Personalization", "Loyalty"], "excursion": ["Upcoming", "Preferences"],
            "dining": ["Preferences", "Personalization"], "package": ["Personalization", "Loyalty"],
            "spa": ["Preferences", "Personalization"], "checkin": ["Upcoming"], "itinerary": ["Upcoming"],
            "service_recovery": ["Upcoming", "Loyalty"], "general": ["Upcoming"]}[intent]
    out = []
    for s in sections:
        if any(s.startswith(w) for w in want):
            out.append({"title": f"Guest profile {profile['guest_id']}", "content": s[:1200], "score": None,
                        "document_id": None, "source": "local-dump"})
    return out


def _local_playbook_chunks(query: str) -> list[dict]:
    q = query.lower()
    scored = []
    for f in knowledge.FAQ:
        s = sum(1 for k in f["keywords"] if k in q)
        if s:
            scored.append((s, f))
    scored.sort(key=lambda x: -x[0])
    return [{"title": "Guest Services Playbook", "content": f"{f['q']} {f['a']}", "answer": f["a"], "score": None,
             "document_id": None, "source": "local-playbook"} for _, f in scored[:3]]


async def _facts(guest_id: str, intent: str) -> dict:
    tool = {"upgrade": "get_upgrade_offers", "service_recovery": "get_upgrade_offers",
            "excursion": "search_shore_excursions"}.get(intent, "get_guest_context")
    res = await tool_gateway.invoke(tool, {"guest_id": guest_id})
    data = res.get("data", res)
    return {"tool": tool, "governed": res.get("governed", False), "trace_id": res.get("trace_id"), "data": data}


def _aom_context_key(guest_id: str, cache_key: str, profile: dict, personal: bool) -> str:
    """Key in AOM's Context Cache. The dump date and (for personal context)
    the profile revision are part of the key, so a new daily dump or any
    booking makes the old entry unreachable at once. Playbook context holds
    no guest data, so every guest shares one entry per intent."""
    if personal:
        return f"{guest_id}:{cache_key}:{profile.get('export_date')}:r{profile.get('rev', 0)}"
    return f"{cache_key}:{profile.get('export_date')}"


def _local_valid(doc: dict | None, profile: dict, personal: bool) -> bool:
    return bool(doc and doc.get("export_date") == profile.get("export_date")
                and (not personal or doc.get("profile_rev") == profile.get("rev", 0)))


async def get_context(guest_id: str, intent: str, profile: dict, personal: bool = True) -> dict:
    """Context Caching, with AOM's Context Cache in front of the assembly.

    1. AOM `/v1/context/get` in the `rag:<app>:guest-context` namespace, so
       hit rate and latency avoided show on AOM's Context Cache and RAG
       Applications pages.
    2. On a miss (or with AOM unreachable), the Couchbase `context_cache`
       document, if it was built from today's dump and the current profile.
    3. Otherwise assemble: KB retrieval scoped to this guest's profile
       document and the playbook, plus live facts from the governed MCP
       tools. The result goes to AOM (`/v1/context/set` with the real build
       time as `source_latency_ms`) and to Couchbase, where the guest's
       channel puts it on the phone for offline answers.
    """
    cache_key = intent if personal else f"playbook_{intent}"
    key = ctx_id(guest_id, cache_key)
    aom_key = _aom_context_key(guest_id, cache_key, profile, personal)
    t0 = time.perf_counter()
    aom_status = "off"
    if aom.enabled:
        try:
            res = await aom.context_get(aom_key, config.CONTEXT_NAMESPACE)
            aom_status = (res.get("cache") or {}).get("status") or ("hit" if res.get("hit") else "miss")
            value = res.get("value")
            if res.get("hit") and isinstance(value, dict):
                # A shared playbook entry may have been stored by another guest's
                # turn: re-home it to this guest before it syncs to their phone.
                doc = dict(value, guest_id=guest_id, channels=[guest_channel(guest_id)])
                local = await store.get("context_cache", key)
                if not _local_valid(local, profile, personal):
                    # Keep the phone's copy current for offline answers.
                    await store.upsert("context_cache", key, doc, ttl=config.CONTEXT_CACHE_TTL_SECONDS)
                doc["_cache"] = {"status": "hit", "source": "aom", "namespace": config.CONTEXT_NAMESPACE,
                                 "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
                return doc
        except AOMError as exc:
            aom_status = "error"
            log.info("AOM context get failed: %s", exc)

    cached = await store.get("context_cache", key)
    if _local_valid(cached, profile, personal):
        cached["_cache"] = {"status": "hit", "source": "couchbase", "aom": aom_status,
                            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
        if aom_status == "miss":
            await _aom_context_set(aom_key, cached, cached.get("build_ms"))
        return cached

    query = INTENT_QUERY[intent]
    guest_doc = await kb_doc_id(guest_id) if personal else None
    playbook_doc = await kb_doc_id("playbook")
    kb_profile, kb_mode = ([], "skipped")
    if personal and intent != "general":
        kb_profile, kb_mode = await _kb(query, guest_doc)
        if not kb_profile:
            kb_profile = _local_profile_chunks(profile, intent)
    kb_playbook, pb_mode = await _kb(query, playbook_doc)
    if not kb_playbook:
        kb_playbook = _local_playbook_chunks(query + " " + intent)
    if kb_mode == "skipped":
        kb_mode = pb_mode
    facts = await _facts(guest_id, intent) if personal and intent != "general" else {}
    build_ms = round((time.perf_counter() - t0) * 1000, 1)
    doc = {
        "type": "context_cache", "guest_id": guest_id, "intent": intent, "personal": personal, "query": query,
        "export_date": profile.get("export_date"), "profile_rev": profile.get("rev", 0),
        "built_at": now_iso(), "build_ms": build_ms, "kb_mode": kb_mode,
        "kb_profile": kb_profile, "kb_playbook": kb_playbook, "facts": facts,
        "guest_document_id": guest_doc, "playbook_document_id": playbook_doc,
        "aom_key": aom_key, "channels": [guest_channel(guest_id)],
    }
    await store.upsert("context_cache", key, doc, ttl=config.CONTEXT_CACHE_TTL_SECONDS)
    await _aom_context_set(aom_key, doc, build_ms)
    doc = dict(doc)
    doc["_cache"] = {"status": "miss", "source": "built", "aom": aom_status, "latency_ms": build_ms}
    return doc


async def _aom_context_set(aom_key: str, doc: dict, build_ms) -> None:
    if not aom.enabled:
        return
    value = {k: v for k, v in doc.items() if not k.startswith("_")}
    if not value.get("personal"):
        if value.get("kb_profile") or value.get("facts"):
            return  # never share guest data across guests
        for k in ("guest_id", "channels", "guest_document_id"):
            value.pop(k, None)
    try:
        await aom.context_set(aom_key, value, config.CONTEXT_NAMESPACE, ttl_seconds=config.CONTEXT_CACHE_TTL_SECONDS,
                              source_latency_ms=int(build_ms or 0))
    except AOMError as exc:
        # 409 = context caching switched off in AOM's policy, 413 = over its size limit.
        log.info("AOM context set skipped: %s", exc)


# --------------------------------------------------------------------------
# Answer composition
# --------------------------------------------------------------------------
def _guest_summary(p: dict) -> str:
    r = p["reservation"]
    return (f"{p['first_name']} {p['last_name']}, Crown & Anchor {p['loyalty']['tier']}. Sailing {r['ship_name']} "
            f"({r['itinerary_name']}) from {r['embark_port']} on {r['embark_date']}, {days_to_sail(p)} days away. "
            f"Party of {r['party_size']}. Stateroom {r['stateroom']['stateroom_number']} "
            f"({r['stateroom']['category_name']}). Check-in: {r['checkin_status']}. Celebrating: "
            f"{p['preferences'].get('celebration') or 'n/a'}. Interests: {', '.join(p['preferences']['interests'])}. "
            f"Dietary: {', '.join(p['preferences']['dietary']) or 'none'}.")


def _facts_text(facts: dict) -> str:
    d = facts.get("data") or {}
    if facts.get("tool") == "get_upgrade_offers":
        rows = [f"{o['category_name']} ({o['category_code']}): {o['available']} left, instant ${o['instant_price_ppn']}"
                f"/person/night (total ${o['instant_total_usd']:,}), RoyalUp min bid ${o['royalup_min_bid_ppn']}"
                + (f", suggested bid ${o['recommended_bid_ppn']}" if o.get("recommended_bid_ppn") else "")
                for o in d.get("offers", [])]
        return "Upgrade options: " + "; ".join(rows)
    if facts.get("tool") == "search_shore_excursions":
        rows = [f"{e['name']} ({e['id']}) at {e['port_name']} on {e['date']}, ${e['price']}/guest"
                + (f", matches {', '.join(e['matched_interests'])}" if e.get("matched_interests") else "")
                for e in d.get("excursions", [])[:6]]
        return "Excursions on this itinerary: " + "; ".join(rows)
    if d:
        return f"Guest context: next best action {d.get('next_best_action')}, purchased {d.get('purchased')}."
    return ""


def build_prompt(message: str, personal: bool, ctx: dict, profile: dict, memories: list[str]) -> str:
    parts = [PERSONA, "", "CONTEXT:"]
    if personal:
        parts.append("Guest: " + _guest_summary(profile))
        for c in ctx.get("kb_profile", [])[:3]:
            parts.append("Profile note: " + (c.get("content") or "")[:900])
        ft = _facts_text(ctx.get("facts") or {})
        if ft:
            parts.append(ft)
        for m in memories[:3]:
            parts.append("Earlier the guest said: " + m[:300])
    for c in ctx.get("kb_playbook", [])[:3]:
        parts.append("Playbook: " + (c.get("content") or "")[:900])
    parts += ["", f"GUEST QUESTION: {message.strip()}", "", "ANSWER:"]
    return "\n".join(parts)


def dining_pick(profile: dict) -> dict | None:
    """The specialty restaurant the concierge suggests: on this guest's ship,
    not already booked, celebration-friendly when they're celebrating, else
    family-friendly for families."""
    r = profile["reservation"]
    owned = set(profile.get("purchased_for_sailing", {}).get("dining", []))
    options = [d for d in C.DINING if C.ship_has_dining(r["ship_code"], d["id"]) and d["id"] not in owned]
    if not options:
        return None
    want = "celebration" if profile["preferences"].get("celebration") else ("family" if r["party_size"] > 2 else "classic")
    return next((d for d in options if want in d["tags"]), options[0])


def compose_fallback(intent: str, personal: bool, message: str, ctx: dict, profile: dict) -> str:
    """Deterministic answer from the same context - used when AOM has no LLM
    provider key (it returns a labelled stub) or AOM is not configured."""
    r = profile["reservation"]
    d = (ctx.get("facts") or {}).get("data") or {}
    first = profile["first_name"]
    if not personal or intent == "general":
        # Answer the question actually asked from the FAQ when it matches;
        # otherwise the best retrieved playbook chunk.
        pb = _local_playbook_chunks(message) or ctx.get("kb_playbook")
        if pb:
            return pb[0].get("answer") or pb[0]["content"]
        return "I can help with upgrades, shore excursions, dining, packages, spa and check-in for your sailing."
    if intent in ("upgrade", "service_recovery"):
        offers = d.get("offers", [])
        rec = next((o for o in offers if o.get("recommended")), offers[0] if offers else None)
        if intent == "service_recovery":
            return (f"I'm so sorry, {first} - that's not the experience we want for you. I can ask a Guest Services "
                    f"supervisor to approve a complimentary move"
                    + (f" to {C.a_or_an(rec['category_name'])}" if rec else "") + ". Tap below to send the request; "
                    "you'll see their decision right here.")
        if not rec:
            return f"You're already in our top available category on {r['ship_name']}, {first}."
        cel = profile["preferences"].get("celebration")
        left = (f"there's only 1 {rec['category_name']} left" if rec["available"] == 1
                else f"there are {rec['available']} {rec['category_name']}s left")
        return (f"Great news, {first} - {left} on {r['ship_name']}"
                + (f", perfect for your {cel}" if cel else "") + f". You can bid with RoyalUp from "
                f"${rec['royalup_min_bid_ppn']}/person/night (we'd suggest "
                f"${rec.get('recommended_bid_ppn') or rec['royalup_min_bid_ppn']}) or upgrade instantly for "
                f"${rec['instant_price_ppn']}/person/night (${rec['instant_total_usd']:,} for your stateroom).")
    if intent == "excursion":
        ex = d.get("excursions", [])[:3]
        if not ex:
            return f"Your itinerary is mostly sea days, {first} - perfect for the spa and pools!"
        lines = "; ".join(f"{e['name']} in {e['port_name'].split(',')[0]} ({e['date']}, ${e['price']})" for e in ex)
        return f"Based on what you love, {first}, here are my top picks: {lines}."
    if intent == "checkin":
        if r["checkin_status"] == "complete":
            return f"You're all checked in, {first}! Arrival time {r.get('arrival_slot')} on {r['embark_date']}."
        return (f"You haven't checked in yet, {first}. It takes about 5 minutes - pick an arrival time for "
                f"{r['embark_date']} and your SetSail Pass will be ready.")
    if intent == "itinerary":
        stops = ", ".join(f"{p['date'][5:]} {p['port'].split(',')[0]}" for p in r["ports"])
        return f"Here's your {r['itinerary_name']} on {r['ship_name']}: {stops}."
    if intent == "dining":
        cel = profile["preferences"].get("celebration")
        pick = dining_pick(profile)
        if not pick:
            return f"You've already reserved every specialty restaurant on {r['ship_name']}, {first} - enjoy!"
        return (f"For {r['ship_name']}, I'd suggest {pick['name']}" + (f" for your {cel}" if cel else "")
                + ". Pick a night and time and I'll pass along your dietary notes.")
    if intent == "spa":
        return "Vitality Spa treatments are 20% off on port days - a great way to unwind while others go ashore."
    if intent == "package":
        return "Based on your past sailings, a package could save you money - see the options below."
    return "Here's what I found for your sailing."


def suggest_actions(intent: str, ctx: dict, profile: dict, message: str) -> list[dict]:
    d = (ctx.get("facts") or {}).get("data") or {}
    r = profile["reservation"]
    acts: list[dict] = []
    if intent == "upgrade":
        offers = d.get("offers", [])
        rec = next((o for o in offers if o.get("recommended")), offers[0] if offers else None)
        if rec and rec["available"] > 0:
            bid = rec.get("recommended_bid_ppn") or rec["royalup_min_bid_ppn"]
            acts.append({"label": f"Bid ${bid}/night · {rec['category_name']}", "tool": "place_royalup_bid",
                         "args": {"category_code": rec["category_code"], "bid_per_night_usd": bid}})
            acts.append({"label": f"Upgrade now · ${rec['instant_total_usd']:,}", "tool": "purchase_cabin_upgrade",
                         "args": {"category_code": rec["category_code"]}})
    elif intent == "service_recovery":
        offers = [o for o in d.get("offers", []) if o.get("available", 0) > 0]
        pick = next((o for o in offers if o.get("recommended")), offers[0] if offers else None)
        if pick:
            acts.append({"label": f"Request complimentary {pick['category_name']}", "tool": "apply_goodwill_upgrade",
                         "args": {"category_code": pick["category_code"],
                                  "reason": f"Guest-reported issue via concierge: {message.strip()[:200]}"}})
    elif intent == "excursion":
        for e in d.get("excursions", [])[:2]:
            if not e.get("already_booked"):
                acts.append({"label": f"Book {e['name']} · ${e['price'] * r['party_size']:,}", "tool": "book_shore_excursion",
                             "args": {"excursion_id": e["id"]}})
    elif intent == "dining":
        pick = dining_pick(profile)
        acts.append({"label": f"Reserve {pick['name']}" if pick else "Reserve a table", "screen": "dining",
                     "args": {"restaurant_id": pick["id"]} if pick else {}})
    elif intent == "spa":
        acts.append({"label": "Book a spa treatment", "screen": "spa"})
    elif intent == "checkin" and r["checkin_status"] != "complete":
        acts.append({"label": "Check in now", "screen": "checkin"})
    elif intent == "package":
        owned = profile.get("purchased_for_sailing", {}).get("packages", [])
        s = profile["ml_scores"]
        ranked = sorted([p for p in C.PACKAGES if p["code"] not in owned], key=lambda p: -s.get(p["propensity"], 0))
        for p in ranked[:2]:
            acts.append({"label": f"Add {p['name']}", "tool": "purchase_package", "args": {"package_code": p["code"]}})
    return acts


# Only durable things the guest says about themselves become memories
# ("we're vegetarian", "my wife loves sushi"). Plain questions don't, which
# also keeps repeat questions' prompts stable for the LLM cache.
STATEMENT_RE = re.compile(r"\b(i|we)('m|'re| am| are| love| like| prefer| hate| don't| do not| want| need| always| never)\b"
                          r"|\bmy (wife|husband|partner|kids?|son|daughter|mom|dad|family)\b|\ballerg", re.I)


async def _remember(guest_id: str, message: str, reply: str, intent: str, session_id: str):
    if not aom.enabled or not STATEMENT_RE.search(message):
        return
    try:
        await aom.memory_add(guest_id, f"Guest said ({intent}): {message.strip()[:500]}", session_id=session_id,
                             metadata={"intent": intent, "app": "rccl-mobile"})
    except AOMError as exc:
        log.info("memory add skipped: %s", exc)


async def _recall(guest_id: str, message: str) -> list[str]:
    if not aom.enabled:
        return []
    try:
        res = await aom.memory_search(guest_id, message, top_k=3)
        return [e.get("content", "") for e in res.get("entries", []) if e.get("content")]
    except AOMError:
        return []


async def _ask_rag_app(message: str, intent: str, profile: dict) -> dict | None:
    """Playbook questions go to the concierge's AOM RAG Application: one call
    that runs AOM's Context Cache (retrieval), the KB search scoped to today's
    playbook, and the LLM Cache, and is counted on the RAG Applications page."""
    if not rag_app.usable():
        return None
    l0 = time.perf_counter()
    try:
        res = await aom.rag_query(config.RAG_APP_ID, message)
    except AOMError as exc:
        rag_app.query_failed(exc)
        log.info("RAG app query failed, answering on the concierge's own path: %s", exc)
        return None
    ms = round((time.perf_counter() - l0) * 1000, 1)
    retrieval = res.get("retrieval") or {}
    llm_res = res.get("llm") or {}
    cache = llm_res.get("cache") or {}
    srcs = res.get("sources") or []
    chunks = [{"title": c.get("document_title"), "content": c.get("preview"), "source": "aom-rag"} for c in srcs]
    reply = (res.get("answer") or "").strip()
    llm = {"status": cache.get("status", "skipped" if not res.get("llm") else "miss"), "similarity": cache.get("similarity"),
           "namespace": f"rag:{config.RAG_APP_ID}", "provider": llm_res.get("provider"), "model": llm_res.get("model"),
           "latency_ms": ms, "stub": bool(llm_res.get("stub")), "tokens_saved": llm_res.get("tokens_saved") or 0,
           "cost_saved_usd": llm_res.get("cost_saved_usd") or 0, "rag_app": config.RAG_APP_ID}
    if not res.get("llm") or llm["stub"] or not reply:
        # No LLM provider key in AOM (stub) or nothing retrieved: answer from
        # the same playbook deterministically.
        reply = compose_fallback(intent, False, message, {"kb_playbook": chunks}, profile)
        llm["composed_locally"] = True
    return {
        "reply": reply, "llm": llm,
        "sources": [{"title": c["title"], "snippet": (c.get("content") or "")[:160], "kind": "aom-rag"} for c in chunks[:3]],
        "context": {"status": retrieval.get("cache", "miss"), "latency_ms": retrieval.get("latency_ms", 0),
                    "source": "aom-rag", "rag_app": config.RAG_APP_ID, "chunks": retrieval.get("chunks"),
                    "export_date": profile.get("export_date"), "kb_mode": "aom"},
        "trace_id": (res.get("trace") or {}).get("trace_id"),
    }


async def ask(guest_id: str, message: str, session_id: str | None = None) -> dict:
    session_id = session_id or f"app-{guest_id}"
    trace_id = uuid.uuid4().hex
    token = current_trace.set({"trace_id": trace_id, "session_id": session_id})
    t0 = time.perf_counter()
    try:
        profile = await store.get("profiles", profile_id(guest_id))
        if not profile:
            raise ValueError("unknown guest")
        intent, personal = classify(message)
        if not personal:
            via_rag = await _ask_rag_app(message, intent, profile)
            if via_rag:
                result = {
                    "reply": via_rag["reply"], "intent": intent, "personal": False, "actions": [],
                    "sources": via_rag["sources"], "context": via_rag["context"], "memory_recalled": 0,
                    "llm": via_rag["llm"], "trace_id": via_rag["trace_id"] or trace_id, "governed": True,
                    "total_ms": round((time.perf_counter() - t0) * 1000, 1), "export_date": STATE.get("export_date"),
                }
                await _append_chat(guest_id, message, result)
                return result
        ctx = await get_context(guest_id, intent, profile, personal)
        memories = await _recall(guest_id, message) if personal else []
        prompt = build_prompt(message, personal, ctx, profile, memories)
        namespace = config.LLM_NAMESPACE_PERSONAL if personal else config.LLM_NAMESPACE_PLAYBOOK
        llm = {"status": "local", "namespace": namespace, "provider": None, "model": None, "similarity": None,
               "latency_ms": None, "stub": False, "tokens_saved": 0}
        reply = None
        if aom.enabled:
            try:
                l0 = time.perf_counter()
                res = await aom.complete(prompt, namespace=namespace)
                cache = res.get("cache") or {}
                llm.update({"status": cache.get("status", "miss"), "similarity": cache.get("similarity"),
                            "provider": res.get("provider"), "model": res.get("model"),
                            "latency_ms": round((time.perf_counter() - l0) * 1000, 1), "stub": bool(res.get("stub")),
                            "tokens_saved": res.get("tokens_saved", 0), "cost_saved_usd": res.get("cost_saved_usd", 0)})
                if not res.get("stub") and (res.get("response") or "").strip():
                    reply = res["response"].strip()
            except AOMError as exc:
                llm["status"] = "error"
                llm["error"] = str(exc)[:200]
        if not reply:
            reply = compose_fallback(intent, personal, message, ctx, profile)
            llm["composed_locally"] = True
        actions = suggest_actions(intent, ctx, profile, message) if personal else []
        sources = ([{"title": c["title"], "snippet": (c.get("content") or "")[:160], "kind": c.get("source")}
                    for c in (ctx.get("kb_profile", []) if personal else [])[:2]]
                   + [{"title": c["title"], "snippet": (c.get("content") or "")[:160], "kind": c.get("source")}
                      for c in ctx.get("kb_playbook", [])[:2]])
        result = {
            "reply": reply, "intent": intent, "personal": personal, "actions": actions, "sources": sources,
            "context": {"status": ctx["_cache"]["status"], "latency_ms": ctx["_cache"]["latency_ms"],
                        "source": ctx["_cache"].get("source"),
                        "built_at": ctx.get("built_at"), "build_ms": ctx.get("build_ms"), "kb_mode": ctx.get("kb_mode"),
                        "export_date": ctx.get("export_date")},
            "memory_recalled": len(memories), "llm": llm, "trace_id": trace_id if aom.enabled else None,
            "governed": aom.enabled, "total_ms": round((time.perf_counter() - t0) * 1000, 1),
            "export_date": STATE.get("export_date"),
        }
        await _append_chat(guest_id, message, result)
        await _remember(guest_id, message, reply, intent, session_id)
        return result
    finally:
        current_trace.reset(token)


async def _append_chat(guest_id: str, message: str, result: dict):
    doc = await store.get("concierge", chat_id(guest_id)) or {
        "type": "concierge", "guest_id": guest_id, "messages": [], "answers": {}, "channels": [guest_channel(guest_id)]}
    now = now_iso()
    doc["messages"] = (doc["messages"] + [
        {"id": uuid.uuid4().hex[:12], "role": "guest", "text": message, "at": now},
        {"id": uuid.uuid4().hex[:12], "role": "concierge", "text": result["reply"], "at": now,
         "intent": result["intent"], "actions": result["actions"], "context": result["context"], "llm": result["llm"],
         "sources": result["sources"]},
    ])[-40:]
    # Answer cache the phone can reuse offline for the same (normalized) question.
    doc["answers"][_norm(message)[:120]] = {"reply": result["reply"], "intent": result["intent"], "at": now}
    if len(doc["answers"]) > 60:
        doc["answers"] = dict(list(doc["answers"].items())[-60:])
    doc["updated_at"] = now
    await store.upsert("concierge", chat_id(guest_id), doc)
