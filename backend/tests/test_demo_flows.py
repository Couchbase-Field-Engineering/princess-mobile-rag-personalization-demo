"""End-to-end checks of the demo backend in memory mode (no Couchbase, no AOM).

    cd backend && pytest -q
"""
import os
import subprocess
import sys
import time
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    dump = tmp_path_factory.mktemp("dump")
    subprocess.run([sys.executable, os.path.join(ROOT, "databricks", "generate_mock_dump.py"),
                    "--export-date", "2026-10-09", "--target-mb", "3", "--out", str(dump)], check=True,
                   capture_output=True)
    os.environ.update(STORE_DRIVER="memory", DUMP_DIR=str(dump), AOM_URL="", SG_ADMIN_URL="")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        for _ in range(50):
            if c.get("/api/health").json()["load"] == "loaded":
                break
            time.sleep(0.1)
        yield c


def login(client, booking, last):
    r = client.post("/api/auth/login", json={"booking_id": booking, "last_name": last})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["guest_id"]


def pull(client, h):
    docs = client.get("/api/sync/pull", headers=h).json()["docs"]
    return {(d["collection"], d["id"]): d["doc"] for d in docs}


def push(client, h, gid, tool, args):
    rid = f"req::{gid}::{uuid.uuid4().hex[:12]}"
    r = client.post("/api/sync/push", headers=h, json={"docs": [{"collection": "requests", "id": rid, "doc": {
        "type": "request", "guest_id": gid, "tool": tool, "args": args, "created_at": "2026-10-09T15:00:00Z"}}]})
    assert r.status_code == 200, r.text
    for _ in range(40):
        d = pull(client, h).get(("requests", rid))
        if d and d["status"] not in ("pending", "processing"):
            return d
        time.sleep(0.1)
    raise AssertionError("request never processed")


def test_personas_and_login(client):
    ps = client.get("/api/demo/personas").json()["personas"]
    assert [p["guest_id"] for p in ps] == ["G00000101", "G00000201", "G00000301"]
    assert client.post("/api/auth/login", json={"booking_id": "4810101", "last_name": "Nope"}).status_code == 401


def test_offers_are_personalized(client):
    h, gid = login(client, "4810101", "Bennett")
    docs = pull(client, h)
    offers = docs[("offers", f"offers::{gid}")]["offers"]
    kinds = [o["kind"] for o in offers]
    assert "checkin" in kinds and "upgrade" in kinds
    up = next(o for o in offers if o["kind"] == "upgrade")
    assert "anniversary" in up["reason"]
    assert ("catalog", "catalog::v1") in docs


def test_concierge_context_cache_and_playbook(client):
    h, gid = login(client, "4830303", "Natarajan")
    a = client.post("/api/concierge", headers=h, json={"message": "Can I upgrade my room?"}).json()
    assert a["intent"] == "upgrade" and a["personal"] and a["context"]["status"] == "miss"
    assert any(x["tool"] == "place_royalup_bid" for x in a["actions"])
    b = client.post("/api/concierge", headers=h, json={"message": "What would an upgrade cost me?"}).json()
    assert b["context"]["status"] == "hit"
    g = client.post("/api/concierge", headers=h, json={"message": "What's included in The Key?"}).json()
    assert g["personal"] is False and "priority" in g["reply"].lower()
    assert ("context_cache", f"ctx::{gid}::upgrade") in pull(client, h)


def test_offline_request_flow_upgrade_and_invalidation(client):
    h, gid = login(client, "4810101", "Bennett")
    client.post("/api/concierge", headers=h, json={"message": "upgrade options for my cabin?"})
    assert ("context_cache", f"ctx::{gid}::upgrade") in pull(client, h)
    r = push(client, h, gid, "purchase_cabin_upgrade", {"category_code": "JS"})
    assert r["status"] == "confirmed", r
    docs = pull(client, h)
    assert docs[("profiles", f"profile::{gid}")]["reservation"]["stateroom"]["category_code"] == "JS"
    # partner's profile moved too
    assert ("context_cache", f"ctx::{gid}::upgrade") not in docs  # invalidated by the booking
    up = [o for o in docs[("offers", f"offers::{gid}")]["offers"] if o["kind"] == "upgrade"]
    assert not up or up[0]["offer_id"] != "upgrade-JS"


def test_business_rule_failures_come_back_on_the_request(client):
    h, gid = login(client, "4820202", "Rivera")
    r = push(client, h, gid, "reserve_specialty_dining", {"restaurant_id": "EMPIRE", "date": "2026-10-12", "time": "19:00"})
    assert r["status"] == "failed" and "isn't on" in r["summary"]
    r = push(client, h, gid, "book_shore_excursion", {"excursion_id": "CCY-THRILL"})
    assert r["status"] == "confirmed" and r["charge_usd"] == 89 * 4
    r = push(client, h, gid, "get_upgrade_offers", {})
    assert r["status"] == "failed"


def test_push_rejects_other_guests(client):
    h, gid = login(client, "4820202", "Rivera")
    r = client.post("/api/sync/push", headers=h, json={"docs": [{"collection": "requests", "id": "req::G00000101::x",
                                                                 "doc": {"guest_id": "G00000101", "tool": "purchase_package"}}]})
    assert r.status_code == 403


def test_dining_availability_matches_bookings(client):
    """The phone only offers seatings the offers doc lists as open; every open
    one books, every full one is refused with alternatives."""
    h, gid = login(client, "4830303", "Natarajan")
    docs = pull(client, h)
    offers = docs[("offers", f"offers::{gid}")]
    prof = docs[("profiles", f"profile::{gid}")]
    full = offers["dining_full"]
    rid = next(iter(full))
    night = prof["reservation"]["ports"][0]["date"]
    times = docs[("catalog", "catalog::v1")]["dining_times"]
    closed = full[rid][night]
    open_ = [t for t in times if t not in closed]
    assert open_, "every night has open seatings"
    ok = push(client, h, gid, "reserve_specialty_dining", {"restaurant_id": rid, "date": night, "time": open_[0]})
    assert ok["status"] == "confirmed", ok
    if closed:
        bad = push(client, h, gid, "reserve_specialty_dining", {"restaurant_id": rid, "date": night, "time": closed[0]})
        assert bad["status"] == "failed" and "fully booked" in bad["summary"]


def test_personas_sail_on_schedule(client):
    """Persona sailings are pinned to the export date: 9, 3 and 2 days out."""
    for booking, last, days in (("4810101", "Bennett", 9), ("4820202", "Rivera", 3), ("4830303", "Natarajan", 2)):
        h, gid = login(client, booking, last)
        r = pull(client, h)[("profiles", f"profile::{gid}")]["reservation"]
        import datetime as dt
        assert (dt.date.fromisoformat(r["embark_date"]) - dt.date(2026, 10, 9)).days == days, (last, r["embark_date"])
