"""Backend for the Princess Cruises personalization demo.

  /api/*          app sign-in (mints a Sync Gateway session), concierge, status,
                  and a REST "preview sync" used only by the browser preview build
  /pcl/mcp/      the pcl-guest-services MCP server AOM governs

Background tasks: the Adobe Real-Time CDP export loader/poller and the offline-first
request worker.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import hmac
import logging
import time

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import adobe, aom_bootstrap, concierge, config, demo_reset, loader, metrics, personalization, rag_app, sgw, worker, workload
from .aom_client import aom
from .docs import (CATALOG_ID, STATE, bookings_id, chat_id, ctx_id, days_to_sail, guest_channel,
                   now_iso, offers_id, profile_id)
from .mcp_server import mcp
from .store import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("pcl.api")

PERSONA_BLURBS = {
    "G00000101": "Captain's Circle Elite celebrating an anniversary - in a Balcony, primed for a suite upgrade.",
    "G00000201": "First-time family of four on a 3-night Princess Cays getaway - excursions, Princess Premier, family upgrade.",
    "G00000301": "Platinum solo wellness traveler sailing in 2 days - spa, Chef's Table, Premium Suite bid.",
}
_bg: list = []


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await store.connect()

    auto_register = config.AOM_AUTO_REGISTER and bool(config.AOM_ADMIN_PASSWORD)

    async def initial_load():
        try:
            # With self-registration the KB is published once AOM sign-in works.
            await loader.load(kb=not auto_register)
        except Exception:  # noqa: BLE001
            log.exception("initial export load failed")

    first = asyncio.create_task(initial_load())
    _bg.append(first)
    if auto_register:
        _bg.append(asyncio.create_task(aom_bootstrap.run(first)))
    _bg.append(asyncio.create_task(worker.loop()))
    _bg.append(asyncio.create_task(loader.poll_forever()))
    async with mcp.session_manager.run():
        yield
    for t in _bg:
        t.cancel()


app = FastAPI(title="Princess Mobile Personalization Demo", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.mount("/pcl", mcp.streamable_http_app())


# --------------------------------------------------------------------------
# auth
# --------------------------------------------------------------------------
def _sign(payload: str) -> str:
    return hmac.new(config.APP_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def make_token(guest_id: str) -> str:
    payload = f"{guest_id}|{int(time.time()) + config.APP_TOKEN_TTL_SECONDS}"
    return base64.urlsafe_b64encode(f"{payload}|{_sign(payload)}".encode()).decode()


def current_guest(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in first")
    try:
        gid, exp, sig = base64.urlsafe_b64decode(authorization.split(" ", 1)[1].encode()).decode().split("|")
    except Exception:  # noqa: BLE001
        raise HTTPException(401, "Invalid session") from None
    if not hmac.compare_digest(sig, _sign(f"{gid}|{exp}")) or int(exp) < time.time():
        raise HTTPException(401, "Session expired - sign in again")
    return gid


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    """Landing page: where everything in the demo lives."""
    rows = [
        ("http://localhost:8081/story", "The story: why Couchbase, not Redis, for an offline-first AI guest app (start here)"),
        ("http://localhost:8081", "The app in a browser (docker compose service <code>web</code>)"),
        ("http://localhost:8200/api/status", "Backend status: Real-Time CDP export load, AEM playbook, Knowledge Base publishing, AOM, Sync Gateway"),
        ("http://localhost:8200/docs", "Backend API (OpenAPI)"),
        ("http://localhost:8200/pcl/mcp", "MCP server <code>pcl-guest-services</code> (called by AOM)"),
        ("http://localhost:18091", "Couchbase Web Console (Administrator / password123)"),
        ("ws://localhost:4984/princess", "Sync Gateway - Couchbase Lite replicates here"),
        ("https://localhost:8090", "Couchbase Agent Operations Manager (its own stack)"),
    ]
    items = "".join(f'<li><a href="{u}">{u}</a> &nbsp;{d}</li>' for u, d in rows)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Princess demo backend</title>
<style>body{{font-family:-apple-system,Arial,sans-serif;max-width:760px;margin:48px auto;padding:0 16px;color:#0B1530}}
h1{{color:#0A1A3F}} li{{margin:10px 0}} a{{color:#16357A;font-weight:600}}</style></head>
<body><h1>Princess Cruises personalization demo</h1>
<p>This is the backend. Open the app at <a href="http://localhost:8081">http://localhost:8081</a>.
Loaded Real-Time CDP export: <b>{STATE.get("export_date") or "loading..."}</b> ({loader.STATUS.get("state")}).</p>
<ul>{items}</ul></body></html>"""


@app.get("/api/health")
async def health():
    return {"status": "ok", "export_date": STATE.get("export_date"), "load": loader.STATUS.get("state")}


@app.get("/api/status")
async def status():
    aom_state = {"configured": aom.enabled, "url": config.AOM_URL or None, "kb_publisher": aom.admin_enabled,
                 "last_error": aom.last_error, "registration": aom_bootstrap.STATUS, "rag_app": dict(rag_app.STATUS, app_id=config.RAG_APP_ID),
                 "context_namespace": config.CONTEXT_NAMESPACE,
                 "dashboard_url": config.AOM_DASHBOARD_URL or None}
    if aom.enabled:
        try:
            aom_state["health"] = await aom.health()
        except Exception as exc:  # noqa: BLE001
            aom_state["health"] = {"error": str(exc)[:200]}
    return {"store": store.driver, "export_date": STATE.get("export_date"),
            "load": {k: v for k, v in loader.STATUS.items()},
            "adobe": {"rtcdp": {**adobe.STATUS["rtcdp"], "export_dir": config.RTCDP_EXPORT_DIR, "sandbox": config.ADOBE_SANDBOX,
                                "identity_namespace": config.ADOBE_RTCDP_IDENTITY_NAMESPACE},
                      "aem": {**adobe.STATUS["aem"], "endpoint": config.AEM_GRAPHQL_ENDPOINT or None}},
            "aom": aom_state, "metrics": metrics.snapshot(),
            "sync_gateway": {"configured": sgw.enabled(), "public_url": config.SG_PUBLIC_URL or None, "db": config.SG_DB},
            "mcp_server": {"server_id": config.AOM_MCP_SERVER_ID, "registered_url": config.AOM_MCP_PUBLIC_URL},
            "workload": {k: v for k, v in workload.status().items()
                         if k in ("state", "run_id", "started_at", "finished_at", "seconds", "done_turns", "total_turns",
                                  "done_guests", "total_guests", "ships_covered", "fleet_size", "total")}}


@app.get("/api/demo/personas")
async def personas():
    out = []
    for gid in loader.PERSONAS:
        p = await store.get("profiles", profile_id(gid))
        if not p:
            continue
        r = p["reservation"]
        out.append({"guest_id": gid, "name": f"{p['first_name']} {p['last_name']}", "last_name": p["last_name"],
                    "booking_id": r["booking_id"], "ship": r["ship_name"], "embark_date": r["embark_date"],
                    "days_to_sail": days_to_sail(p), "tier": p["loyalty"]["tier"],
                    "stateroom": r["stateroom"]["category_name"], "blurb": PERSONA_BLURBS.get(gid, "")})
    return {"personas": out, "export_date": STATE.get("export_date")}


class LoginRequest(BaseModel):
    booking_id: str
    last_name: str


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    idx = await store.get("lookups", f"booking::{req.booking_id.strip()}")
    if not idx or req.last_name.strip().lower() not in idx.get("last_names", []):
        raise HTTPException(401, "We couldn't find that reservation. Check the booking number and last name.")
    ln = req.last_name.strip().lower()
    guest_id = None
    for gid in idx["guests"]:
        p = await store.get("profiles", profile_id(gid))
        if p and p["last_name"].lower() == ln and (p["reservation"].get("lead_guest") or guest_id is None):
            guest_id = gid
            if p["reservation"].get("lead_guest"):
                break
    await personalization.refresh_offers(guest_id)
    profile = await store.get("profiles", profile_id(guest_id))
    sg = await sgw.mint_session(guest_id)
    return {"token": make_token(guest_id), "guest_id": guest_id,
            "guest": {"first_name": profile["first_name"], "last_name": profile["last_name"],
                      "tier": profile["loyalty"]["tier"], "email": profile.get("email")},
            "channels": [guest_channel(guest_id), "catalog"], "sync_gateway": sg,
            "export_date": STATE.get("export_date")}


@app.post("/api/auth/refresh")
async def refresh(guest_id: str = Depends(current_guest)):
    """Re-mint the Sync Gateway session (24h) for a signed-in guest - called by
    the app on launch when it has connectivity."""
    await personalization.refresh_offers(guest_id)
    return {"token": make_token(guest_id), "guest_id": guest_id, "sync_gateway": await sgw.mint_session(guest_id),
            "export_date": STATE.get("export_date")}


@app.get("/api/me")
async def me(guest_id: str = Depends(current_guest)):
    return await store.get("profiles", profile_id(guest_id))


async def _guest_docs(guest_id: str) -> list[dict]:
    out = []
    for col, key in (("profiles", profile_id(guest_id)), ("offers", offers_id(guest_id)),
                     ("bookings", bookings_id(guest_id)), ("concierge", chat_id(guest_id)), ("catalog", CATALOG_ID)):
        d = await store.get(col, key)
        if d:
            out.append({"collection": col, "id": key, "doc": d})
    for key in concierge.CONTEXT_KEYS:
        d = await store.get("context_cache", ctx_id(guest_id, key))
        if d:
            out.append({"collection": "context_cache", "id": ctx_id(guest_id, key), "doc": d})
    for d in await store.requests_for_guest(guest_id):
        key = d.pop("_id")
        out.append({"collection": "requests", "id": key, "doc": d})
    return out


@app.get("/api/sync/pull")
async def sync_pull(guest_id: str = Depends(current_guest)):
    """Browser-preview stand-in for Sync Gateway: the same documents and ids
    the guest's channels would replicate into Couchbase Lite."""
    return {"docs": await _guest_docs(guest_id), "at": now_iso(), "export_date": STATE.get("export_date")}


class PushDoc(BaseModel):
    collection: str
    id: str
    doc: dict


class PushRequest(BaseModel):
    docs: list[PushDoc] = Field(default_factory=list)


@app.post("/api/sync/push")
async def sync_push(req: PushRequest, guest_id: str = Depends(current_guest)):
    """Browser-preview stand-in for a push replication. Same rule the Sync
    Gateway sync function enforces: a guest may only create `requests`
    documents, only for themselves, only as `pending`."""
    accepted = []
    for d in req.docs:
        if d.collection != "requests" or d.doc.get("guest_id") != guest_id or not d.id.startswith(f"req::{guest_id}::"):
            raise HTTPException(403, "Only your own action requests can be pushed")
        if await store.get("requests", d.id):
            continue
        doc = {**d.doc, "type": "request", "status": "pending", "channels": [guest_channel(guest_id)],
               "received_at": now_iso()}
        await store.upsert("requests", d.id, doc)
        accepted.append(d.id)
    if accepted:
        _bg.append(asyncio.create_task(worker.run_once()))
    return {"accepted": accepted}


class AskRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.post("/api/concierge")
async def ask(req: AskRequest, guest_id: str = Depends(current_guest)):
    if not req.message.strip():
        raise HTTPException(400, "Ask me something")
    return await concierge.ask(guest_id, req.message[:1000], req.session_id)


# --------------------------------------------------------------------------
# demo: fleet chatbot workload (see workload.py)
# --------------------------------------------------------------------------
class WorkloadRequest(BaseModel):
    guests_per_ship: int = Field(3, ge=1, le=1000)   # 17 ships x this many sessions
    turns_per_guest: int = Field(6, ge=2, le=30)
    concurrency: int = Field(4, ge=1, le=64)
    ships: list[str] | None = None          # catalog codes, e.g. ["SUN", "STR"]; default: the whole fleet
    seed: int = 7
    repeat_ratio: float = Field(0.5, ge=0, le=1)      # guests who ask their personal question twice (exact hit)
    paraphrase_ratio: float = Field(0.3, ge=0, le=1)  # turns that reword a question (semantic hit)
    window_days: int = Field(45, ge=1, le=150)        # pick guests sailing within this many days
    pace_ms: int = Field(0, ge=0, le=5000)            # pause between a guest's turns
    duration_hours: float | None = Field(None, gt=0, le=168)  # spread the run over this long, day/night curve


@app.post("/api/demo/workload")
async def workload_start(req: WorkloadRequest):
    """Start the fleet chatbot workload against AOM: guests from every
    Princess ship ask the concierge what passengers ask, through the real
    RAG app / Context Cache / LLM Cache / Agent Memory path. Poll GET for
    progress; the outcome shows on AOM's LLM Cache, Context Cache, RAG
    Applications and Traces pages."""
    try:
        return await workload.start(**req.model_dump())
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(409 if "already running" in str(exc) else 400, str(exc)) from None


@app.get("/api/demo/workload")
async def workload_status():
    return workload.status()


@app.delete("/api/demo/workload")
async def workload_stop():
    return await workload.stop()


@app.get("/api/demo/workload/plan")
async def workload_plan(guests_per_ship: int = 1, turns_per_guest: int = 6, seed: int = 7, window_days: int = 45,
                        ships: str | None = None):
    """Preview who would ask what, without running anything."""
    codes = [c.strip().upper() for c in ships.split(",")] if ships else None
    try:
        guests = await workload.pick_guests(guests_per_ship, codes, window_days, seed)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
    return {"sessions": workload.plan(guests, turns_per_guest, seed), "export_date": STATE.get("export_date")}


@app.get("/api/demo/workload/catalog")
async def workload_catalog():
    """The fleet and the passenger use cases the workload draws from."""
    return workload.catalog()


# --------------------------------------------------------------------------
# demo: reset (see demo_reset.py)
# --------------------------------------------------------------------------
class ResetRequest(BaseModel):
    guests: list[str] | None = None   # default: the personas + everyone who changed something since the load
    aom_memory: bool = True           # delete the guests' AOM Agent Memory entries
    aom_caches: bool = True           # purge the concierge's LLM / Context Cache namespaces in AOM
    counters: bool = True             # zero the in-process counters and forget the last workload report


@app.post("/api/demo/reset")
async def demo_reset_run(req: ResetRequest):
    """Back to the state of today's export: requests, chat, cached context,
    stateroom/check-in/purchases, offers - here and on the phone via Sync
    Gateway - plus the guests' AOM memories and the concierge's AOM caches."""
    if workload.RUN.get("state") == "running":
        raise HTTPException(409, "a fleet workload is running - stop it first (DELETE /api/demo/workload)")
    return await demo_reset.run(req.guests, req.aom_memory, req.aom_caches, req.counters)


@app.get("/api/demo/reset")
async def demo_reset_last():
    return {"last": demo_reset.LAST, "default_guests": await demo_reset.default_guests()}


@app.post("/api/admin/reload")
async def reload_export(force: bool = True):
    return {k: v for k, v in (await loader.load(force=force)).items()}
