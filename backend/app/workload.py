"""Fleet chatbot workload - a demo of AOM's LLM Cache and Context Cache under
a realistic Princess guest-concierge load.

`POST /api/demo/workload` (or scripts/run_chatbot_workload.py) plays a crowd
of guests from every ship in the fleet against the concierge, exactly the way
the mobile app does: each guest gets a session, asks the things a cruise
passenger asks before and during a sailing, and every turn runs the real
concierge path - AOM RAG Application for playbook questions, AOM Context
Cache + Knowledge Base + governed MCP tools for personal ones, AOM Agent
Memory for what the guest says about themselves, and AOM `/v1/llm/complete`
in the `rag:princess-guest-concierge:*` namespaces for generation. Nothing is
stubbed here; the point is to make AOM's LLM Cache, Context Cache, RAG
Applications and Traces pages fill up with a workload that looks like
production.

How the traffic is shaped (what makes the caches hit the way they would in
production):

* **Playbook questions** (packages, check-in, dress code, gratuities, ...)
  are drawn Zipf-style from USE_CASES, so a few questions dominate - as in a
  real support queue. Most guests use the canonical wording (exact hits once
  the first guest has paid for the answer), a minority reword it (semantic
  hits), and the long tail misses.
* **Personal questions** build a per-guest, per-intent context once
  (`Context cache: built`) and the follow-up in the same intent reuses it
  (`hit`). Asking the very same thing again in a session is an exact LLM hit;
  a reworded follow-up shares the context but needs a (semantically cached)
  completion.
* **Statements** ("we're vegetarian", "my wife loves sushi") go to Agent
  Memory and are recalled on that guest's later turns.

The run is in-process (it calls `concierge.ask` directly), so it needs no
app sessions, and it reports per ship, per use case and per cache outcome.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import math
import random
import time
from zoneinfo import ZoneInfo

from . import catalog as C
from . import concierge, config
from .aom_client import aom
from .docs import STATE, profile_id
from .store import store

log = logging.getLogger("pcl.workload")

# --------------------------------------------------------------------------
# What passengers ask. `personal` questions take the guest's own data path
# (context cache); the rest go to the RAG application over the playbook.
# `weight` is the share of the queue (Zipf-ish), `variants[0]` is the wording
# most guests use; the others are paraphrases for semantic hits.
# --------------------------------------------------------------------------
USE_CASES: list[dict] = [
    # --- before the cruise: documents, check-in, boarding -------------------------
    {"id": "checkin_how", "intent": "checkin", "personal": False, "weight": 10,
     "variants": ["What do I need for check-in?", "How does online check-in work?",
                  "What is OceanReady and how do I complete it?", "Is there anything to do before boarding day?"]},
    {"id": "checkin_mine", "intent": "checkin", "personal": True, "weight": 8,
     "variants": ["Am I checked in for my cruise?", "Have we finished check-in yet?",
                  "Can you check my check-in status and arrival time?"]},
    {"id": "arrival_time", "intent": "checkin", "personal": False, "weight": 8,
     "variants": ["What time should I arrive at the terminal?", "When can boarding start on embarkation day?",
                  "How early should we get to the port?"]},
    {"id": "documents", "intent": "checkin", "personal": False, "weight": 6,
     "variants": ["What documents do I need to board?", "Do I need a passport for this cruise?",
                  "Is a birth certificate enough to sail?"]},
    {"id": "medallion", "intent": "package", "personal": False, "weight": 5,
     "variants": ["How does the Medallion work?", "What is the Medallion used for on board?",
                  "Does my Medallion open the stateroom door?"]},
    {"id": "luggage", "intent": "general", "personal": False, "weight": 4,
     "variants": ["How much luggage can I bring?", "Where do I get luggage tags?",
                  "Can I carry my own bags on board?"]},
    {"id": "parking", "intent": "general", "personal": False, "weight": 3,
     "variants": ["Is there parking at the cruise terminal?", "How much does port parking cost?"]},
    # --- staterooms & upgrades ---------------------------------------------------
    {"id": "upgrade_how", "intent": "upgrade", "personal": False, "weight": 9,
     "variants": ["How does Princess Upgrade work?", "How do upgrade bids work?",
                  "Can you explain the Princess Upgrade bidding program?"]},
    {"id": "upgrade_mine", "intent": "upgrade", "personal": True, "weight": 9,
     "variants": ["Can we upgrade to a suite?", "Is there a bigger stateroom available for my sailing?",
                  "What would it cost to move my cabin up a category?"]},
    {"id": "upgrade_followup", "intent": "upgrade", "personal": True, "weight": 7, "followup_of": "upgrade_mine",
     "variants": ["What would the Premium Suite cost for my cruise?", "How much is the balcony upgrade for us?",
                  "What is the minimum bid I can place?"]},
    {"id": "suite_perks", "intent": "upgrade", "personal": False, "weight": 4,
     "variants": ["What are the suite perks?", "What is included with a Premium Suite?",
                  "Do suites get priority boarding?"]},
    # --- shore excursions ----------------------------------------------------------
    {"id": "excursion_mine", "intent": "excursion", "personal": True, "weight": 9,
     "variants": ["What shore excursions do you recommend for my ports?", "What can we do in port on our cruise?",
                  "Which tours match what we like?"]},
    {"id": "excursion_kids", "intent": "excursion", "personal": True, "weight": 4, "followup_of": "excursion_mine",
     "variants": ["Which excursions are good for my kids?", "Anything on our itinerary that works for a family?",
                  "What's the best beach day for us?"]},
    {"id": "princess_cays", "intent": "excursion", "personal": False, "weight": 6,
     "variants": ["What is Princess Cays?", "Is Princess Cays a private island?", "What is there to do at Princess Cays?"]},
    {"id": "excursion_cancel", "intent": "excursion", "personal": False, "weight": 3,
     "variants": ["Can I cancel a shore excursion?", "What is the excursion cancellation policy?",
                  "Do I get a refund if the ship skips a port?"]},
    # --- dining ---------------------------------------------------------------------
    {"id": "dining_mine", "intent": "dining", "personal": True, "weight": 8,
     "variants": ["Where should we have our anniversary dinner?", "Which specialty restaurant do you suggest for us?",
                  "Can you book a table for my family one night?"]},
    {"id": "dining_time", "intent": "dining", "personal": False, "weight": 6,
     "variants": ["Can I change my dining time?", "How do I switch to anytime dining?",
                  "Is traditional dining still offered?"]},
    {"id": "dietary", "intent": "dining", "personal": False, "weight": 5,
     "variants": ["Can the restaurants handle a gluten-free diet?", "Are vegetarian options available at dinner?",
                  "How do I tell the ship about a food allergy?"]},
    {"id": "dress_code", "intent": "general", "personal": False, "weight": 7,
     "variants": ["What is the dress code for dinner?", "How many formal nights are there?",
                  "Do I need a jacket for formal night?"]},
    # --- packages: drinks, Wi-Fi, Plus / Premier ---------------------------------------
    {"id": "premier", "intent": "package", "personal": False, "weight": 10,
     "variants": ["What's included in Princess Premier?", "What do I get with the Premier package?",
                  "Premier vs Plus - what is the difference?"]},
    {"id": "beverage", "intent": "package", "personal": False, "weight": 8,
     "variants": ["Who needs a beverage package?", "Is the drink package worth it?",
                  "How many drinks a day make the Plus package pay off?"]},
    {"id": "wifi", "intent": "package", "personal": False, "weight": 7,
     "variants": ["Is Wi-Fi available on board?", "How good is MedallionNet for video calls?",
                  "Can I stream Netflix at sea?"]},
    {"id": "package_mine", "intent": "package", "personal": True, "weight": 6,
     "variants": ["Which package makes sense for us?", "Should I add Princess Plus to my booking?",
                  "Do we already have Wi-Fi included?"]},
    {"id": "zero_alcohol", "intent": "package", "personal": False, "weight": 3,
     "variants": ["Is there a non-alcoholic drink package?", "What does the Zero-Alcohol package include?"]},
    # --- spa & wellness ----------------------------------------------------------------
    {"id": "spa_port_day", "intent": "spa", "personal": False, "weight": 5,
     "variants": ["Are spa treatments cheaper on port days?", "Does the Lotus Spa discount on port days?",
                  "When is the best time to book a massage?"]},
    {"id": "spa_mine", "intent": "spa", "personal": True, "weight": 4,
     "variants": ["Can you book me a massage on a sea day?", "I'd like a couples massage on our cruise - options?",
                  "Which spa treatment would you suggest for me?"]},
    {"id": "fitness", "intent": "spa", "personal": False, "weight": 3,
     "variants": ["Is the fitness center free?", "Are yoga classes included?", "What are the thermal suite hours?"]},
    # --- itinerary & the ship -----------------------------------------------------------
    {"id": "itinerary_mine", "intent": "itinerary", "personal": True, "weight": 8,
     "variants": ["What's my itinerary?", "Which ports do we visit and when?", "When is our first sea day?"]},
    {"id": "port_times", "intent": "itinerary", "personal": True, "weight": 5, "followup_of": "itinerary_mine",
     "variants": ["What time do we need to be back on board in port?", "How long are we docked at each port on my cruise?",
                  "Do we tender anywhere on our itinerary?"]},
    {"id": "kids", "intent": "general", "personal": False, "weight": 6,
     "variants": ["Are kids' activities included?", "What is Camp Discovery?", "Is there a teen lounge on board?"]},
    {"id": "gratuities", "intent": "general", "personal": False, "weight": 6,
     "variants": ["How much are gratuities?", "Is crew appreciation included in my fare?",
                  "Can I prepay tips?"]},
    {"id": "smoking", "intent": "general", "personal": False, "weight": 2,
     "variants": ["Where can I smoke on board?", "Is vaping allowed on the balcony?"]},
    {"id": "laundry", "intent": "general", "personal": False, "weight": 2,
     "variants": ["Is there a laundromat on the ship?", "How much does laundry service cost?"]},
    {"id": "casino", "intent": "general", "personal": False, "weight": 2,
     "variants": ["When does the casino open?", "Can I use my Medallion to play in the casino?"]},
    {"id": "currency", "intent": "general", "personal": False, "weight": 3,
     "variants": ["What currency is used on board?", "Can I pay with cash on the ship?",
                  "Is there an ATM on board?"]},
    {"id": "medical", "intent": "general", "personal": False, "weight": 3,
     "variants": ["Is there a doctor on board?", "Can I bring my prescription medication?",
                  "What should I do if I get seasick?"]},
    {"id": "accessibility", "intent": "general", "personal": False, "weight": 2,
     "variants": ["Are there wheelchair-accessible staterooms?", "Can I rent a scooter for the cruise?"]},
    {"id": "loyalty", "intent": "general", "personal": False, "weight": 4,
     "variants": ["What are the Captain's Circle benefits?", "What do Elite members get?",
                  "How do I reach Platinum?"]},
    {"id": "celebration", "intent": "dining", "personal": False, "weight": 3,
     "variants": ["Can you arrange a birthday celebration on board?", "Do you offer anniversary packages?",
                  "How do I order a cake for our cabin?"]},
    {"id": "oceannow", "intent": "package", "personal": False, "weight": 3,
     "variants": ["What is OceanNow delivery?", "Can I order food to the pool deck?",
                  "Is OceanNow included with Princess Plus?"]},
    {"id": "cancellation", "intent": "general", "personal": False, "weight": 3,
     "variants": ["What is the cancellation policy?", "Can I buy travel insurance through Princess?",
                  "When is final payment due?"]},
    # --- service recovery (approval-tier goodwill upgrade) ---------------------------------
    {"id": "service_recovery", "intent": "service_recovery", "personal": True, "weight": 2,
     "variants": ["Our cabin is right under the pool deck and really noisy, can you help?",
                  "The air conditioning in my room isn't working.",
                  "My stateroom smelled of smoke when we arrived, I'm disappointed."]},
]
USE_CASE_BY_ID = {u["id"]: u for u in USE_CASES}

# What guests tell the concierge about themselves - written to AOM Agent
# Memory, recalled on their later personal turns.
STATEMENTS = [
    "We're vegetarian, so please keep that in mind for dinner.", "My wife loves sushi.",
    "I'm celebrating my 40th birthday on this cruise.", "We always prefer a quiet table away from the kitchen.",
    "My son is allergic to peanuts.", "I don't like early mornings, so no 7am tours please.",
    "We love snorkeling and anything in the water.", "My husband needs a wheelchair-accessible tour.",
    "I never eat shellfish.", "We prefer small-group excursions.",
]

RUN: dict = {"state": "idle"}
_TASK: asyncio.Task | None = None


def _normalize_outcome(llm: dict) -> str:
    """AOM reports `hit_exact`, `hit_semantic` or `miss` (plus bypass/error)."""
    st = (llm or {}).get("status") or "local"
    if st.startswith("hit"):
        return "exact_hit" if st in ("hit", "hit_exact") or (llm.get("similarity") or 0) >= 0.999 else "semantic_hit"
    if st == "miss":
        return "miss"
    return st  # local / error / skipped / bypass


class _Plan:
    """The passengers and their questions, before anything runs."""

    def __init__(self, guests: list[dict], turns_per_guest: int, seed: int, repeat_ratio: float, paraphrase_ratio: float):
        self.rng = random.Random(seed)
        self.guests = guests
        self.turns = turns_per_guest
        self.repeat_ratio = repeat_ratio
        self.paraphrase_ratio = paraphrase_ratio
        self.playbook = [u for u in USE_CASES if not u["personal"]]
        self.personal_openers = [u for u in USE_CASES if u["personal"] and not u.get("followup_of")]
        self.followups = {}
        for u in USE_CASES:
            if u.get("followup_of"):
                self.followups.setdefault(u["followup_of"], []).append(u)

    def _phrase(self, uc: dict) -> str:
        v = uc["variants"]
        if len(v) > 1 and self.rng.random() < self.paraphrase_ratio:
            return self.rng.choice(v[1:])
        return v[0]

    def _pick_playbook(self) -> dict:
        return self.rng.choices(self.playbook, weights=[u["weight"] for u in self.playbook])[0]

    def session(self, guest: dict) -> list[dict]:
        """One guest's conversation: a statement, a personal thread (open +
        follow-up + maybe repeat), the rest playbook questions."""
        rng = self.rng
        turns: list[dict] = []
        if rng.random() < 0.5:
            turns.append({"use_case": "statement", "intent": "memory", "personal": True, "message": rng.choice(STATEMENTS)})
        opener = rng.choices(self.personal_openers, weights=[u["weight"] for u in self.personal_openers])[0]
        first = self._phrase(opener)
        turns.append({"use_case": opener["id"], "intent": opener["intent"], "personal": True, "message": first})
        fu = self.followups.get(opener["id"])
        if fu:
            f = rng.choice(fu)
            turns.append({"use_case": f["id"], "intent": f["intent"], "personal": True, "message": self._phrase(f)})
        if rng.random() < self.repeat_ratio:
            turns.append({"use_case": opener["id"], "intent": opener["intent"], "personal": True, "message": first,
                          "repeat": True})
        while len(turns) < self.turns:
            uc = self._pick_playbook()
            turns.append({"use_case": uc["id"], "intent": uc["intent"], "personal": False, "message": self._phrase(uc)})
        return turns[: max(self.turns, 2)]


async def pick_guests(guests_per_ship: int, ships: list[str] | None, window_days: int, seed: int) -> list[dict]:
    export_date = STATE.get("export_date")
    if not export_date:
        raise RuntimeError("no Real-Time CDP export loaded yet")
    today = dt.date.fromisoformat(config.DEMO_TODAY or export_date)
    rows = await store.guests_sailing_between(today.isoformat(), (today + dt.timedelta(days=window_days)).isoformat())
    rng = random.Random(seed)
    rng.shuffle(rows)
    want = set(ships or C.SHIPS)
    by_ship: dict[str, list[dict]] = {}
    # Lead guests first (they hold the booking), then anyone.
    for r in sorted(rows, key=lambda r: not r.get("lead_guest")):
        code = r.get("ship_code")
        if code in want and len(by_ship.setdefault(code, [])) < guests_per_ship:
            by_ship[code].append(r)
    out = []
    for code in C.SHIPS:
        for r in by_ship.get(code, []):
            out.append({"guest_id": r["guest_id"], "ship_code": code, "ship_name": C.SHIPS[code]["name"],
                        "embark_date": r.get("embark_date")})
    return out


def plan(guests: list[dict], turns_per_guest=6, seed=7, repeat_ratio=0.5, paraphrase_ratio=0.3) -> list[dict]:
    p = _Plan(guests, turns_per_guest, seed, repeat_ratio, paraphrase_ratio)
    return [{**g, "turns": p.session(g)} for g in guests]


def _empty_bucket() -> dict:
    return {"turns": 0, "llm_exact_hit": 0, "llm_semantic_hit": 0, "llm_miss": 0, "llm_other": 0,
            "context_hit": 0, "context_miss": 0, "rag_app": 0, "memory_writes": 0, "errors": 0,
            "tokens_saved": 0, "cost_saved_usd": 0.0, "latency_ms_total": 0.0}


def _count(bucket: dict, rec: dict):
    bucket["turns"] += 1
    o = rec["llm_outcome"]
    bucket[{"exact_hit": "llm_exact_hit", "semantic_hit": "llm_semantic_hit", "miss": "llm_miss"}.get(o, "llm_other")] += 1
    if rec.get("context") == "hit":
        bucket["context_hit"] += 1
    elif rec.get("context") in ("miss", "built"):
        bucket["context_miss"] += 1
    if rec.get("path") == "rag_app":
        bucket["rag_app"] += 1
    if rec.get("use_case") == "statement":
        bucket["memory_writes"] += 1
    if rec.get("error"):
        bucket["errors"] += 1
    bucket["tokens_saved"] += rec.get("tokens_saved") or 0
    bucket["cost_saved_usd"] = round(bucket["cost_saved_usd"] + (rec.get("cost_saved_usd") or 0), 6)
    bucket["latency_ms_total"] += rec.get("latency_ms") or 0


def _finish_bucket(b: dict) -> dict:
    cacheable = b["llm_exact_hit"] + b["llm_semantic_hit"] + b["llm_miss"]
    ctx = b["context_hit"] + b["context_miss"]
    b["llm_hit_rate"] = round(100 * (b["llm_exact_hit"] + b["llm_semantic_hit"]) / cacheable, 1) if cacheable else None
    b["context_hit_rate"] = round(100 * b["context_hit"] / ctx, 1) if ctx else None
    b["avg_latency_ms"] = round(b["latency_ms_total"] / b["turns"], 1) if b["turns"] else None
    return b


async def _one_turn(guest: dict, turn: dict, session_id: str) -> dict:
    t0 = time.perf_counter()
    rec = {"guest_id": guest["guest_id"], "ship_code": guest["ship_code"], "ship_name": guest["ship_name"],
           "use_case": turn["use_case"], "expected_intent": turn["intent"], "message": turn["message"],
           "repeat": bool(turn.get("repeat"))}
    try:
        res = await concierge.ask(guest["guest_id"], turn["message"], session_id)
        llm = res.get("llm") or {}
        ctx = res.get("context") or {}
        rec.update({
            "intent": res.get("intent"), "personal": res.get("personal"),
            "path": "rag_app" if ctx.get("source") == "aom-rag" else ("personal" if res.get("personal") else "playbook"),
            "llm_status": llm.get("status"), "llm_outcome": _normalize_outcome(llm), "similarity": llm.get("similarity"),
            "stub": bool(llm.get("stub")), "provider": llm.get("provider"), "model": llm.get("model"),
            "tokens_saved": llm.get("tokens_saved") or 0, "cost_saved_usd": llm.get("cost_saved_usd") or 0,
            "context": ctx.get("status"), "context_source": ctx.get("source"),
            "memory_recalled": res.get("memory_recalled", 0), "trace_id": res.get("trace_id"),
            "reply": (res.get("reply") or "")[:160],
        })
    except Exception as exc:  # noqa: BLE001 - one failing turn must not stop the fleet
        rec.update({"error": str(exc)[:200], "llm_outcome": "error", "path": "error"})
    rec["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return rec


# A day in a guest-services queue: relative traffic per local hour (0-23).
# Quiet overnight, a morning ramp, steady afternoon, peak after dinner when
# guests plan the next day, tailing off late. Used when a run is spread over
# `duration_hours` so the AOM charts look like a real queue, not a metronome.
DIURNAL = [0.25, 0.18, 0.15, 0.15, 0.2, 0.35, 0.6, 0.85, 1.0, 1.1, 1.15, 1.15,
           1.1, 1.05, 1.0, 1.0, 1.1, 1.3, 1.5, 1.6, 1.5, 1.2, 0.8, 0.45]
WORKLOAD_TZ = ZoneInfo("America/New_York")


def _traffic_integral(start: dt.datetime, hours: float) -> float:
    """Area under the diurnal curve from `start` for `hours` (hour-weights)."""
    total, t = 0.0, start
    remaining = hours
    while remaining > 1e-9:
        step = min(remaining, 1.0 - (t.minute * 60 + t.second) / 3600.0)
        total += DIURNAL[t.hour] * step
        t += dt.timedelta(hours=step)
        remaining -= step
    return total


class _Pacer:
    """Holds the fleet to a schedule: by `elapsed` hours the run should have
    completed total_turns * (traffic so far / traffic over the whole run)."""

    def __init__(self, total_turns: int, duration_hours: float):
        self.total = total_turns
        self.hours = duration_hours
        self.start = dt.datetime.now(WORKLOAD_TZ)
        self.whole = _traffic_integral(self.start, duration_hours) or 1.0

    def target(self, now: dt.datetime | None = None) -> int:
        now = now or dt.datetime.now(WORKLOAD_TZ)
        elapsed = min(self.hours, max(0.0, (now - self.start).total_seconds() / 3600.0))
        return int(self.total * _traffic_integral(self.start, elapsed) / self.whole)

    async def wait(self, done: int):
        """Sleep until the schedule allows the next turn (polling, so Stop works)."""
        while done >= self.target() and not RUN.get("cancel"):
            if (dt.datetime.now(WORKLOAD_TZ) - self.start).total_seconds() / 3600.0 >= self.hours:
                return
            await asyncio.sleep(2)


async def _run(sessions: list[dict], concurrency: int, pace_ms: int, duration_hours: float | None = None):
    sem = asyncio.Semaphore(max(1, concurrency))
    by_ship = {s["ship_code"]: _empty_bucket() | {"ship_name": s["ship_name"], "guests": 0} for s in sessions}
    by_use_case: dict[str, dict] = {}
    by_path: dict[str, dict] = {}
    total = _empty_bucket()
    recent: list[dict] = []
    RUN.update(by_ship=by_ship, by_use_case=by_use_case, by_path=by_path, total=total, recent=recent, done_turns=0,
               done_guests=0)
    pacer = _Pacer(RUN["total_turns"], duration_hours) if duration_hours else None
    if pacer:
        RUN["ends_at"] = (pacer.start + dt.timedelta(hours=duration_hours)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    async def one_guest(s: dict):
        async with sem:
            by_ship[s["ship_code"]]["guests"] += 1
            session_id = f"workload-{RUN['run_id']}-{s['guest_id']}"
            for turn in s["turns"]:
                if RUN.get("cancel"):
                    return
                if pacer:
                    await pacer.wait(RUN["done_turns"])
                    if RUN.get("cancel"):
                        return
                rec = await _one_turn(s, turn, session_id)
                for b in (total, by_ship[s["ship_code"]], by_use_case.setdefault(rec["use_case"], _empty_bucket()),
                          by_path.setdefault(rec["path"], _empty_bucket())):
                    _count(b, rec)
                recent.append(rec)
                del recent[:-40]
                RUN["done_turns"] += 1
                if pace_ms:
                    await asyncio.sleep(pace_ms / 1000)
            RUN["done_guests"] += 1

    t0 = time.time()
    try:
        await asyncio.gather(*(one_guest(s) for s in sessions))
        RUN["state"] = "cancelled" if RUN.get("cancel") else "done"
    except asyncio.CancelledError:
        RUN["state"] = "cancelled"
        raise
    except Exception as exc:  # noqa: BLE001
        RUN.update(state="error", error=str(exc)[:300])
        log.exception("workload failed")
    finally:
        RUN["seconds"] = round(time.time() - t0, 1)
        RUN["finished_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for b in [total, *by_ship.values(), *by_use_case.values(), *by_path.values()]:
            _finish_bucket(b)
        log.info("Fleet workload %s: %s turns in %.1fs - LLM hit rate %s%%, context hit rate %s%%", RUN["state"],
                 total["turns"], RUN["seconds"], total["llm_hit_rate"], total["context_hit_rate"])


async def start(guests_per_ship=3, turns_per_guest=6, concurrency=4, ships: list[str] | None = None, seed: int = 7,
                repeat_ratio=0.5, paraphrase_ratio=0.3, window_days=45, pace_ms=0,
                duration_hours: float | None = None) -> dict:
    """`duration_hours` spreads the run over that long (e.g. 24) following the
    DIURNAL curve; otherwise it runs as fast as `concurrency` allows."""
    global _TASK
    if RUN.get("state") == "running":
        raise RuntimeError("a workload is already running - stop it first (DELETE /api/demo/workload)")
    unknown = [s for s in (ships or []) if s not in C.SHIPS]
    if unknown:
        raise ValueError(f"unknown ship code(s): {', '.join(unknown)}; fleet is {', '.join(C.SHIPS)}")
    guests = await pick_guests(guests_per_ship, ships, window_days, seed)
    if not guests:
        raise RuntimeError(f"no guests sailing within {window_days} days of {STATE.get('export_date')}")
    sessions = plan(guests, turns_per_guest, seed, repeat_ratio, paraphrase_ratio)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    RUN.clear()
    RUN.update(state="running", run_id=run_id, started_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               params={"guests_per_ship": guests_per_ship, "turns_per_guest": turns_per_guest, "concurrency": concurrency,
                       "ships": ships or sorted(C.SHIPS), "seed": seed, "repeat_ratio": repeat_ratio,
                       "paraphrase_ratio": paraphrase_ratio, "window_days": window_days, "pace_ms": pace_ms,
                       "duration_hours": duration_hours},
               total_guests=len(sessions), total_turns=sum(len(s["turns"]) for s in sessions),
               ships_covered=sorted({s["ship_code"] for s in sessions}), fleet_size=len(C.SHIPS),
               aom={"configured": aom.enabled, "url": config.AOM_URL or None, "dashboard_url": config.AOM_DASHBOARD_URL or None,
                    "rag_app": config.RAG_APP_ID, "llm_namespaces": [config.LLM_NAMESPACE_PLAYBOOK, config.LLM_NAMESPACE_PERSONAL],
                    "context_namespace": config.CONTEXT_NAMESPACE},
               export_date=STATE.get("export_date"))
    if duration_hours:
        RUN["ends_at"] = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=duration_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _TASK = asyncio.create_task(_run(sessions, concurrency, pace_ms, duration_hours))
    return status()


def status() -> dict:
    out = dict(RUN)
    out.pop("cancel", None)
    if out.get("state") == "running":
        if out.get("params", {}).get("duration_hours") and out.get("started_at"):
            started = dt.datetime.strptime(out["started_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
            out["elapsed_hours"] = round((dt.datetime.now(dt.timezone.utc) - started).total_seconds() / 3600, 2)
        # live rates while it runs
        out["total"] = _finish_bucket(dict(out.get("total") or _empty_bucket()))
        out["by_ship"] = {k: _finish_bucket(dict(v)) for k, v in (out.get("by_ship") or {}).items()}
    return out


async def stop() -> dict:
    if RUN.get("state") == "running":
        RUN["cancel"] = True
        if _TASK:
            try:
                await asyncio.wait_for(asyncio.shield(_TASK), timeout=30)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                _TASK.cancel()
    return status()


def catalog() -> dict:
    """The scenario, for the story page and the CLI: ships and use cases."""
    return {
        "fleet": [{"code": c, "name": s["name"], "class": s["class"], "home_port": C.PORTS[s["home_port"]],
                   "itineraries": [C.ITINERARIES[i]["name"] for i in C.SHIP_ITINERARIES[c]]} for c, s in C.SHIPS.items()],
        "use_cases": [{k: v for k, v in u.items()} for u in USE_CASES],
        "statements": STATEMENTS,
    }
