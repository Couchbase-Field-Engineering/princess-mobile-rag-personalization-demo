#!/usr/bin/env python3
"""Run the Princess fleet chatbot workload against AOM and watch it land.

Drives the demo backend's `POST /api/demo/workload`: guests from every ship
in the Princess fleet ask the Guest Concierge what passengers ask (check-in,
upgrades, excursions, dining, packages, spa, itinerary, policies, a noisy
cabin...), through the real path - AOM RAG Application, Context Cache,
Knowledge Base, governed MCP tools, Agent Memory and `/v1/llm/complete`. Then
open AOM's LLM Cache and Context Cache pages: that is the workload.

    # the deployment on mother (backend :8201, AOM dashboard :3111)
    python scripts/run_chatbot_workload.py
    # bigger / faster / a few ships only
    python scripts/run_chatbot_workload.py --guests-per-ship 6 --turns 8 --concurrency 8 --ships SUN,STR,ENC
    # local docker compose
    python scripts/run_chatbot_workload.py --backend http://localhost:8200 --aom https://localhost:8090

Only the Python standard library is needed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BACKEND = "http://192.168.111.4:8201"
DEFAULT_AOM = "https://192.168.111.4:3111"


def call(base: str, path: str, method="GET", body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:400]
        sys.exit(f"{method} {path} -> HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        sys.exit(f"Cannot reach {base}{path}: {exc.reason}")


def pct(v):
    return "-" if v is None else f"{v:>5.1f}%"


def bar(done, total, width=28):
    n = int(width * done / total) if total else 0
    return "[" + "#" * n + "." * (width - n) + "]"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", default=DEFAULT_BACKEND, help=f"demo backend (default {DEFAULT_BACKEND})")
    ap.add_argument("--aom", default=DEFAULT_AOM, help=f"AOM dashboard, for the links printed at the end (default {DEFAULT_AOM})")
    ap.add_argument("--guests-per-ship", type=int, default=3)
    ap.add_argument("--turns", type=int, default=6, help="turns per guest session")
    ap.add_argument("--concurrency", type=int, default=4, help="guests chatting at the same time")
    ap.add_argument("--ships", help="comma-separated catalog codes (default: the whole fleet)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--repeat-ratio", type=float, default=0.5)
    ap.add_argument("--paraphrase-ratio", type=float, default=0.3)
    ap.add_argument("--window-days", type=int, default=45)
    ap.add_argument("--pace-ms", type=int, default=0)
    ap.add_argument("--hours", type=float, help="spread the run over this many hours with a day/night traffic curve "
                    "(e.g. --guests-per-ship 300 --concurrency 4 --hours 24); the script can be Ctrl-C'd, the run continues")
    ap.add_argument("--plan", action="store_true", help="print who would ask what, run nothing")
    ap.add_argument("--stop", action="store_true", help="stop a running workload")
    ap.add_argument("--status", action="store_true", help="show the current/last run and exit")
    ap.add_argument("--json", action="store_true", help="print the final report as JSON")
    a = ap.parse_args()

    if a.stop:
        print(json.dumps(call(a.backend, "/api/demo/workload", "DELETE"), indent=1)[:2000]); return
    if a.status:
        print(json.dumps(call(a.backend, "/api/demo/workload"), indent=1)[:6000]); return

    st = call(a.backend, "/api/status")
    aom = st.get("aom") or {}
    print(f"Backend {a.backend}: export {st.get('export_date')}, store {st.get('store')}")
    print(f"AOM: {aom.get('url')} - {'registered' if (aom.get('registration') or {}).get('state') == 'registered' else (aom.get('registration') or {}).get('state')}"
          f", RAG app {(aom.get('rag_app') or {}).get('app_id')} {(aom.get('rag_app') or {}).get('state')}")
    if not aom.get("configured"):
        print("WARNING: the backend has no AOM configured - the concierge will answer locally and nothing will reach AOM.")

    ships = [s.strip().upper() for s in a.ships.split(",")] if a.ships else None
    if a.plan:
        q = f"?guests_per_ship={a.guests_per_ship}&turns_per_guest={a.turns}&seed={a.seed}&window_days={a.window_days}"
        if ships:
            q += "&ships=" + ",".join(ships)
        sessions = call(a.backend, "/api/demo/workload/plan" + q)["sessions"]
        for s in sessions:
            print(f"\n{s['ship_name']} ({s['ship_code']}) - guest {s['guest_id']}, sails {s['embark_date']}")
            for t in s["turns"]:
                print(f"   {'personal' if t['personal'] else 'playbook':8} {t['use_case']:18} {t['message']}")
        print(f"\n{len(sessions)} sessions, {sum(len(s['turns']) for s in sessions)} turns")
        return

    body = {"guests_per_ship": a.guests_per_ship, "turns_per_guest": a.turns, "concurrency": a.concurrency,
            "ships": ships, "seed": a.seed, "repeat_ratio": a.repeat_ratio, "paraphrase_ratio": a.paraphrase_ratio,
            "window_days": a.window_days if not a.hours else max(a.window_days, 150), "pace_ms": a.pace_ms,
            "duration_hours": a.hours}
    run = call(a.backend, "/api/demo/workload", "POST", body)
    print(f"\nStarted run {run['run_id']}: {run['total_guests']} guests on {len(run['ships_covered'])}/{run['fleet_size']} ships, "
          f"{run['total_turns']} turns, {a.concurrency} concurrent sessions"
          + (f", paced over {a.hours} h (day/night curve), ends {run.get('ends_at')}" if a.hours else "") + "\n")
    try:
        while run.get("state") == "running":
            time.sleep(1.5)
            run = call(a.backend, "/api/demo/workload")
            t = run.get("total") or {}
            line = (f"\r{bar(run.get('done_turns', 0), run.get('total_turns', 1))} {run.get('done_turns', 0)}/{run.get('total_turns')} turns  "
                    f"LLM hit {pct(t.get('llm_hit_rate'))}  context hit {pct(t.get('context_hit_rate'))}  "
                    f"tokens saved {t.get('tokens_saved', 0):,}  errors {t.get('errors', 0)}   ")
            sys.stdout.write(line); sys.stdout.flush()
    except KeyboardInterrupt:
        if a.hours:
            print(f"\nDetached - the run continues on the backend until {run.get('ends_at')}; --status to check, --stop to end it.")
            return
        print("\nStopping ...")
        run = call(a.backend, "/api/demo/workload", "DELETE")
    print()
    if a.json:
        print(json.dumps(run, indent=1)); return

    t = run.get("total") or {}
    print(f"\nRun {run.get('run_id')} {run.get('state')} in {run.get('seconds')}s - {t.get('turns')} turns, "
          f"{run.get('done_guests')} guests, {len(run.get('ships_covered') or [])} ships")
    print(f"  LLM Cache:     {t.get('llm_exact_hit', 0)} exact + {t.get('llm_semantic_hit', 0)} semantic hits, "
          f"{t.get('llm_miss', 0)} provider calls  -> hit rate {pct(t.get('llm_hit_rate'))}")
    print(f"  Context Cache: {t.get('context_hit', 0)} hits, {t.get('context_miss', 0)} builds  -> hit rate {pct(t.get('context_hit_rate'))}")
    print(f"  RAG app turns: {t.get('rag_app', 0)}   memory writes: {t.get('memory_writes', 0)}   "
          f"tokens saved: {t.get('tokens_saved', 0):,}   est. cost saved: ${t.get('cost_saved_usd', 0):.4f}   errors: {t.get('errors', 0)}")

    print(f"\n  {'Ship':22} {'guests':>6} {'turns':>5} {'LLM hit':>8} {'ctx hit':>8} {'tokens':>7} {'avg ms':>7}")
    for code, b in sorted((run.get("by_ship") or {}).items(), key=lambda kv: kv[1]["ship_name"]):
        print(f"  {b['ship_name']:22} {b['guests']:>6} {b['turns']:>5} {pct(b.get('llm_hit_rate')):>8} "
              f"{pct(b.get('context_hit_rate')):>8} {b.get('tokens_saved', 0):>7,} {b.get('avg_latency_ms') or 0:>7.0f}")

    print(f"\n  {'Use case':20} {'turns':>5} {'exact':>5} {'seman':>5} {'miss':>5} {'ctx hit':>8}")
    for uc, b in sorted((run.get("by_use_case") or {}).items(), key=lambda kv: -kv[1]["turns"])[:20]:
        print(f"  {uc:20} {b['turns']:>5} {b['llm_exact_hit']:>5} {b['llm_semantic_hit']:>5} {b['llm_miss']:>5} {pct(b.get('context_hit_rate')):>8}")

    recent = run.get("recent") or []
    stub = any(r.get("stub") for r in recent)
    if stub:
        print("\n  Note: AOM answered with labelled stubs (no LLM provider key configured) - the caches still count hits, "
              "the concierge composed the replies locally.")
    print(f"\nNow open AOM:\n  LLM Cache        {a.aom}/llm-caching\n  Context Cache    {a.aom}/context-cache\n"
          f"  RAG Applications {a.aom}/rag-applications\n  Traces           {a.aom}/traces\n  Agent Memory     {a.aom}/memory")


if __name__ == "__main__":
    main()
