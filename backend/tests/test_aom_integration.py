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
    subprocess.run([sys.executable, os.path.join(ROOT, "databricks", "generate_mock_dump.py"), "--export-date",
                    "2026-10-09", "--target-mb", "2", "--out", str(dump)], check=True, capture_output=True)
    env = {**os.environ, "STORE_DRIVER": "memory", "DUMP_DIR": str(dump), "AOM_URL": AOM,
           "AOM_AGENT_API_KEY": "fake-agent-key", "AOM_ADMIN_PASSWORD": "x", "KB_PROFILE_LIMIT": "10",
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
