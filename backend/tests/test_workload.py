"""The fleet chatbot workload (app/workload.py) in memory mode: every ship
gets passengers, every turn goes through the concierge, the report adds up.

    cd backend && pytest -q tests/test_workload.py
"""
import time

from app import catalog as C


def _wait(client):
    for _ in range(600):
        run = client.get("/api/demo/workload").json()
        if run["state"] != "running":
            return run
        time.sleep(0.1)
    raise AssertionError("workload did not finish")


def test_catalog_covers_the_fleet(client):
    cat = client.get("/api/demo/workload/catalog").json()
    assert len(cat["fleet"]) == len(C.SHIPS) == 17
    ids = [u["id"] for u in cat["use_cases"]]
    assert len(ids) == len(set(ids))
    intents = {u["intent"] for u in cat["use_cases"]}
    assert {"checkin", "upgrade", "excursion", "dining", "package", "spa", "itinerary", "service_recovery", "general"} <= intents


def test_plan_has_a_session_per_ship(client):
    plan = client.get("/api/demo/workload/plan?guests_per_ship=1&turns_per_guest=6&window_days=150").json()["sessions"]
    assert {s["ship_code"] for s in plan} == set(C.SHIPS)
    for s in plan:
        assert len(s["turns"]) == 6
        assert any(t["personal"] for t in s["turns"]) and any(not t["personal"] for t in s["turns"])


def test_workload_runs_the_fleet_and_reports(client):
    r = client.post("/api/demo/workload", json={"guests_per_ship": 1, "turns_per_guest": 5, "concurrency": 6,
                                               "window_days": 150, "seed": 3, "pace_ms": 100})
    assert r.status_code == 200, r.text
    started = r.json()
    assert started["state"] == "running" and started["total_turns"] == 17 * 5
    # a second start while running is refused (pace_ms keeps the first one busy)
    assert client.post("/api/demo/workload", json={"window_days": 150}).status_code == 409
    run = _wait(client)
    assert run["state"] == "done", run.get("error")
    t = run["total"]
    assert t["turns"] == 85 and t["errors"] == 0
    assert sum(b["turns"] for b in run["by_ship"].values()) == 85
    assert set(run["by_ship"]) == set(C.SHIPS)
    assert sum(b["turns"] for b in run["by_use_case"].values()) == 85
    # no AOM in tests: the LLM is answered locally, but context caching still happens in Couchbase/memory
    assert t["llm_other"] == 85 and t["context_hit"] + t["context_miss"] > 0
    assert run["recent"] and all(rec["reply"] for rec in run["recent"])
    # status summary is on /api/status for the story page
    assert client.get("/api/status").json()["workload"]["state"] == "done"


def test_unknown_ship_is_rejected(client):
    r = client.post("/api/demo/workload", json={"ships": ["TITANIC"], "window_days": 150})
    assert r.status_code == 400 and "unknown ship" in r.text
