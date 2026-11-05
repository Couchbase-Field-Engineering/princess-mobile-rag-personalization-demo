"""The AOM-governed path, against tests/fake_aom.py (same routes and shapes as
the real AOM): KB publishing, document-scoped retrieval, LLM cache across
guests, tool calls over real MCP, and the human-approval tier.
"""
import os
import subprocess
import sys
import time
import uuid

import httpx
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
AOM, API = "http://127.0.0.1:18090", "http://127.0.0.1:18201"


def wait(url, tries=80):
    for _ in range(tries):
        try:
            if httpx.get(url, timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"{url} never came up")


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    dump = tmp_path_factory.mktemp("dump")
    subprocess.run([sys.executable, os.path.join(ROOT, "adobe", "generate_mock_export.py"), "--export-date",
                    "2026-10-09", "--target-mb", "2", "--out", str(dump)], check=True, capture_output=True)
    env = {**os.environ, "STORE_DRIVER": "memory", "RTCDP_EXPORT_DIR": str(dump), "ADOBE_MOCK_LATENCY_MS": "1,2", "AOM_URL": AOM,
           "AOM_AGENT_API_KEY": "fake-agent-key", "AOM_UPGRADE_AGENT_API_KEY": "fake-agent-key", "AOM_ADMIN_PASSWORD": "x", "KB_PROFILE_LIMIT": "10",
           "SG_ADMIN_URL": "", "REQUEST_POLL_SECONDS": "0.3", "FAKE_MCP_URL": f"{API}/pcl/mcp"}
    uv = [sys.executable, "-m", "uvicorn"]
    procs = [subprocess.Popen(uv + ["tests.fake_aom:app", "--port", "18090"], cwd=BACKEND, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)]
    wait(f"{AOM}/api/health")
    procs.append(subprocess.Popen(uv + ["app.main:app", "--port", "18201"], cwd=BACKEND, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    wait(f"{API}/api/health")
    for _ in range(60):
        st = httpx.get(f"{API}/api/status").json()
        if (st["load"].get("kb") or {}).get("state") == "published":
            break
        time.sleep(0.25)
    yield
    for p in procs:
        p.terminate()


def login(booking, last):
    r = httpx.post(f"{API}/api/auth/login", json={"booking_id": booking, "last_name": last})
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["guest_id"]


def ask(h, q):
    return httpx.post(f"{API}/api/concierge", headers=h, json={"message": q}, timeout=30).json()


def test_kb_published_and_scoped(stack):
    titles = list(httpx.get(f"{AOM}/test/state").json()["docs"].values())
    assert any(t.startswith("Guest Services Playbook") for t in titles)
    assert any("G00000101" in t for t in titles)
    h, gid = login("4810101", "Bennett")
    a = ask(h, "Can we upgrade to a suite?")
    assert a["context"]["kb_mode"] == "aom" and a["governed"]
    searched = [c[1] for c in httpx.get(f"{AOM}/test/state").json()["calls"] if c[0] == "kb_search"]
    assert all(d is not None for d in searched), "every KB search must be scoped to one document"


def test_llm_cache_shared_for_playbook_only(stack):
    h1, _ = login("4810101", "Bennett")
    h2, _ = login("4830303", "Natarajan")
    a = ask(h1, "How does Princess Upgrade work?")
    b = ask(h2, "How does Princess Upgrade work?")
    assert a["personal"] is False and b["llm"]["status"] == "hit_exact"
    p1 = ask(h1, "Can I upgrade my stateroom?")
    p2 = ask(h2, "Can I upgrade my stateroom?")
    assert p1["llm"]["namespace"] == "rag:princess-guest-concierge:personal" and p2["llm"]["status"] == "miss"


def test_rag_application_registered_and_scoped_to_playbook(stack):
    st = httpx.get(f"{AOM}/test/state").json()
    app = st["rag_apps"]["princess-guest-concierge"]
    playbook = [d for d, t in st["docs"].items() if t.startswith("Guest Services Playbook")]
    assert app["enabled"] and app["document_ids"] == playbook
    assert set(app["allowed_roles"]) == {"support_agent", "admin"}

    h, _ = login("4830303", "Natarajan")
    q = "What's included in Princess Premier?"
    a, b = ask(h, q), ask(h, q)
    assert a["context"]["source"] == "aom-rag" and a["llm"]["rag_app"] == "princess-guest-concierge"
    assert b["context"]["status"] == "hit" and b["llm"]["status"] == "hit_exact"
    assert "Princess Premier" in a["reply"] and a["sources"]
    rag = [c for c in httpx.get(f"{AOM}/test/state").json()["calls"] if c[0] == "rag_query"]
    # Playbook answers never retrieve a guest's profile.
    assert rag and all(set(c[3]) <= set(playbook) for c in rag)


def test_personal_context_cached_in_aom(stack):
    h, gid = login("4810101", "Bennett")
    q = "What does my itinerary look like?"
    first, second = ask(h, q), ask(h, q)
    assert second["context"]["status"] == "hit" and second["context"]["source"] == "aom"
    calls = httpx.get(f"{AOM}/test/state").json()["calls"]
    sets = [c for c in calls if c[0] == "ctx_set" and c[2].startswith(f"{gid}:itinerary:")]
    assert sets and sets[0][1] == "rag:princess-guest-concierge:guest-context" and sets[0][3] is not None
    # A booking bumps the profile revision, so the next turn misses and rebuilds.
    assert first["context"]["status"] in ("miss", "hit")


def test_goodwill_upgrade_waits_for_human(stack):
    h, gid = login("4820202", "Rivera")
    rid = f"req::{gid}::{uuid.uuid4().hex[:8]}"
    httpx.post(f"{API}/api/sync/push", headers=h, json={"docs": [{"collection": "requests", "id": rid, "doc": {
        "type": "request", "guest_id": gid, "tool": "apply_goodwill_upgrade",
        "args": {"category_code": "OV", "reason": "AC not working in stateroom"}, "created_at": "2026-10-09T15:00:00Z"}}]})

    def req():
        docs = httpx.get(f"{API}/api/sync/pull", headers=h).json()["docs"]
        return next(d["doc"] for d in docs if d["id"] == rid)

    for _ in range(30):
        if req()["status"] == "awaiting_approval":
            break
        time.sleep(0.2)
    doc = req()
    assert doc["status"] == "awaiting_approval" and doc["governed"]
    httpx.post(f"{AOM}/test/approve/{doc['approval_id']}")
    for _ in range(30):
        if req()["status"] == "confirmed":
            break
        time.sleep(0.2)
    assert req()["status"] == "confirmed"


def test_confirm_upgrade_runs_the_upgrade_agent_with_memory(stack):
    """Confirm on the upgrade screen -> a purchase_cabin_upgrade request -> the
    Stateroom Upgrade Agent runs it through AOM and writes to Agent Memory, which
    the concierge then recalls."""
    h, gid = login("4830303", "Natarajan")
    before = httpx.get(f"{AOM}/test/state").json()["memory"]
    rid = f"req::{gid}::{uuid.uuid4().hex[:8]}"
    httpx.post(f"{API}/api/sync/push", headers=h, json={"docs": [{"collection": "requests", "id": rid, "doc": {
        "type": "request", "guest_id": gid, "tool": "purchase_cabin_upgrade", "title": "Upgrade now",
        "args": {"category_code": "PS"}, "created_at": "2026-10-09T15:00:00Z"}}]})

    def req():
        docs = httpx.get(f"{API}/api/sync/pull", headers=h).json()["docs"]
        return next(d["doc"] for d in docs if d["id"] == rid)

    for _ in range(40):
        if req()["status"] in ("confirmed", "failed"):
            break
        time.sleep(0.2)
    doc = req()
    assert doc["status"] == "confirmed", doc
    assert doc["governed"] and doc["agent"] == "princess-upgrade-agent" and doc["remembered"] is True
    assert httpx.get(f"{AOM}/test/state").json()["memory"] > before
    a = ask(h, "Can we upgrade our stateroom again next time?")
    assert a["memory_recalled"] >= 1


def test_fleet_workload_hits_aom_caches(stack):
    """The fleet workload through the fake AOM: playbook questions repeat
    across guests (exact LLM hits), personal follow-ups reuse the guest's
    context (context hits), and the CLI reports it."""
    body = {"guests_per_ship": 1, "turns_per_guest": 6, "concurrency": 4, "window_days": 150, "seed": 11}
    r = httpx.post(f"{API}/api/demo/workload", json=body, timeout=30)
    assert r.status_code == 200, r.text
    for _ in range(600):
        run = httpx.get(f"{API}/api/demo/workload").json()
        if run["state"] != "running":
            break
        time.sleep(0.2)
    assert run["state"] == "done", run.get("error")
    t = run["total"]
    assert t["errors"] == 0 and t["turns"] == 17 * 6
    assert t["llm_exact_hit"] > 0, t           # the same playbook question from a second guest
    assert t["llm_miss"] > 0                    # the first guest paid for it
    assert t["context_hit"] > 0                 # follow-ups in the same intent reuse the guest's context
    assert t["rag_app"] > 0                     # playbook questions went to the RAG application
    assert len(run["by_ship"]) == 17
    # the CLI summarizes the same run
    out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "run_chatbot_workload.py"),
                          "--backend", API, "--status"], capture_output=True, text=True, check=True).stdout
    assert '"state": "done"' in out


def test_demo_reset_clears_aom_memory_and_caches(stack):
    """After the workload and a chat that wrote a memory, the reset deletes
    the guests' AOM memories, purges the concierge namespaces, and the next
    question is a cache miss again."""
    h, gid = login("4810101", "Bennett")
    ask(h, "We're vegetarian and my wife loves sushi.")          # -> AOM Agent Memory
    assert httpx.get(f"{AOM}/v1/memory", params={"user_id": gid}, headers={"Authorization": "Bearer fake-agent-key"}).json()["count"] >= 1
    ask(h, "What's included in Princess Premier?")
    res = httpx.post(f"{API}/api/demo/reset", json={}, timeout=60).json()
    assert res["state"] == "done", res
    me = next(g for g in res["guests"] if g["guest_id"] == gid)
    assert me["memories"] >= 1 and "memory_error" not in me
    assert httpx.get(f"{AOM}/v1/memory", params={"user_id": gid}, headers={"Authorization": "Bearer fake-agent-key"}).json()["count"] == 0
    assert "error" not in res["aom_caches"], res["aom_caches"]
    assert sum(v.get("llm_purged", 0) for v in res["aom_caches"].values()) >= 1
    a = ask(h, "What's included in Princess Premier?")
    assert a["llm"]["status"] == "miss"
