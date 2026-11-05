"""The demo reset (app/demo_reset.py) in memory mode: after an upgrade and a
chat, a persona is back to the export - requests gone, stateroom restored,
context and chat cleared, offers re-ranked.

    cd backend && pytest -q tests/test_reset.py
"""
from test_demo_flows import login, pull, push


def test_reset_restores_the_persona(client):
    h, gid = login(client, "4810101", "Bennett")
    client.post("/api/concierge", headers=h, json={"message": "upgrade options for my cabin?"})
    r = push(client, h, gid, "purchase_cabin_upgrade", {"category_code": "PS"})
    assert r["status"] == "confirmed", r
    docs = pull(client, h)
    assert docs[("profiles", f"profile::{gid}")]["reservation"]["stateroom"]["category_code"] == "PS"
    assert any(c == "requests" for c, _ in docs) and ("concierge", f"chat::{gid}") in docs
    assert gid in client.get("/api/demo/reset").json()["default_guests"]

    res = client.post("/api/demo/reset", json={}).json()
    assert res["state"] == "done"
    me = next(g for g in res["guests"] if g["guest_id"] == gid)
    assert me["profile"] == "reloaded" and me["requests"] >= 1 and "concierge" in me["docs"]
    assert res["summary"]["profiles_reloaded"] >= 3        # the three personas at least

    docs = pull(client, h)
    p = docs[("profiles", f"profile::{gid}")]
    # Olivia's export stateroom is a Balcony - whatever earlier tests (or demos) did to it
    assert p["reservation"]["stateroom"]["category_code"] == "BA" and p["rev"] == 0
    assert not any(c == "requests" for c, _ in docs)
    assert ("concierge", f"chat::{gid}") not in docs and ("context_cache", f"ctx::{gid}::upgrade") not in docs
    assert ("offers", f"offers::{gid}") in docs            # re-ranked from the restored profile
    # the suite the upgrade took is back on sale
    up = [o for o in docs[("offers", f"offers::{gid}")]["offers"] if o["kind"] == "upgrade"]
    assert up, "upgrade offers should be back after the reset"
    assert client.get("/api/status").json()["metrics"]["concierge_turns"] == 0
