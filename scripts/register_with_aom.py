#!/usr/bin/env python3
"""Register the Princess Cruises demo with the Couchbase Agent Operations Manager.

Idempotent. Standard library only. Does five things through AOM's API, signed
in as an AOM dashboard admin:

  1. Registers this backend's MCP server `pcl-guest-services` as a trusted
     server (POST /v1/servers) - or re-ingests it if it is already registered -
     so AOM pulls its 11 tools into the vetted catalog, open to the
     `support_agent` and `admin` roles.
  2. Issues two agent identities (POST /v1/agents, role support_agent):
     **Princess Guest Concierge**, scoped to all 11 tools, and **Princess Stateroom
     Upgrade Agent**, scoped to the 5 upgrade tools and written to .env as
     AOM_UPGRADE_AGENT_API_KEY (it runs every Confirm on the upgrade screen and
     keeps the outcome in AOM Agent Memory). The concierge key is issued
     `support_agent`, scoped to exactly those 11 tools) and writes its API key
     into ../.env as AOM_AGENT_API_KEY. With --rotate, rotates the key of an
     existing agent instead.
  3. Turns on AOM's human-approval tier for `pcl-guest-services::apply_goodwill_upgrade`
     (complimentary upgrades wait for a supervisor), leaving every other
     approval setting as it was.
  4. Registers the concierge as the RAG Application `princess-guest-concierge`
     (POST /v1/rag/apps, or PUT if it exists), queryable by the
     `support_agent` and `admin` roles and scoped to the Guest Services
     Playbook document. Its activity (queries, LLM cache hits, Context Cache
     retrievals) shows on AOM's RAG Applications page. The backend re-points
     it at each day's new playbook document after the daily load.
  5. Writes AOM_ADMIN_* into ../.env so the backend's daily loader can publish
     Knowledge Base documents and manage the RAG application.

    python scripts/register_with_aom.py --aom-url https://localhost:8090 \
        --admin-user admin --admin-password '<your AOM admin password>'
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, "..", ".env")
SERVER_ID = "pcl-guest-services"
AGENT_NAME = "Princess Guest Concierge"
TOOLS = ["get_guest_context", "get_upgrade_offers", "place_upgrade_bid", "purchase_cabin_upgrade",
         "apply_goodwill_upgrade", "search_shore_excursions", "book_shore_excursion", "reserve_specialty_dining",
         "purchase_package", "book_spa_treatment", "complete_online_checkin"]
APPROVAL_TOOLS = [f"{SERVER_ID}::apply_goodwill_upgrade"]
RAG_APP_ID = "princess-guest-concierge"
UPGRADE_AGENT_NAME = "Princess Stateroom Upgrade Agent"
UPGRADE_TOOLS = ["get_guest_context", "get_upgrade_offers", "place_upgrade_bid", "purchase_cabin_upgrade",
                 "apply_goodwill_upgrade"]
UPGRADE_DESCRIPTION = ("Princess Cruises stateroom upgrade agent. Triggered when a guest confirms an upgrade in the "
                       "mobile app: recalls the guest's stateroom history and preferences from Agent Memory, applies "
                       "the upgrade, bid or complimentary move as a governed tool call, and remembers the outcome.")
# Keep in step with backend/app/rag_app.py, which owns the definition at runtime.
RAG_SYSTEM_PROMPT = (
    "You are the Princess Cruises Guest Concierge in the guest's mobile app. Answer the guest's question "
    "warmly and concisely (under 120 words) using only the numbered Guest Services Playbook passages. Never "
    "invent prices, availability or bookings. Cite the passages you used as [1], [2]. If the passages do not "
    "answer the question, say you'll connect the guest with Guest Services."
)


def rag_app_definition(playbook_id):
    return {
        "app_id": RAG_APP_ID,
        "name": "Princess Guest Concierge (mobile)",
        "description": ("Princess Cruises mobile app concierge. Playbook questions are answered here from the "
                        "daily Guest Services Playbook. Personal answers use the guest's own profile from the "
                        "Adobe Real-Time CDP export, cached in the guest-context namespace."),
        "owner": "Princess Digital Guest Experience",
        # Never enabled without a document scope: unscoped, a support_agent
        # query could retrieve any guest's profile.
        "enabled": bool(playbook_id),
        "allowed_roles": ["support_agent", "admin"],
        "set_id": "default",
        "document_ids": [playbook_id] if playbook_id else [],
        "top_k": 4,
        "retrieval_ttl_seconds": 6 * 3600,
        "semantic_cache": True,
        "system_prompt": RAG_SYSTEM_PROMPT,
        "no_answer_text": "I couldn't find that in our Guest Services Playbook. I can connect you with Guest Services.",
    }


class Api:
    def __init__(self, base: str, verify: bool):
        self.base = base.rstrip("/")
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                                  urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, body=None, ok=(200, 201, 202)):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=180) as r:
                txt = r.read().decode() or "{}"
                return r.status, json.loads(txt)
        except urllib.error.HTTPError as e:
            txt = e.read().decode()
            try:
                payload = json.loads(txt)
            except json.JSONDecodeError:
                payload = {"detail": txt}
            if e.code in ok:
                return e.code, payload
            return e.code, payload


def set_env(updates: dict):
    lines = open(ENV_PATH).read().splitlines() if os.path.exists(ENV_PATH) else []
    seen = set()
    for i, line in enumerate(lines):
        k = line.split("=", 1)[0].strip()
        if k in updates:
            lines[i] = f"{k}={updates[k]}"
            seen.add(k)
    lines += [f"{k}={v}" for k, v in updates.items() if k not in seen]
    with open(ENV_PATH, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def die(msg):
    print(f"\n✗ {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aom-url", default=os.getenv("AOM_URL_HOST", "https://localhost:8090"),
                    help="AOM as reachable from THIS machine")
    ap.add_argument("--admin-user", default=os.getenv("AOM_ADMIN_USERNAME", "admin"))
    ap.add_argument("--admin-password", default=os.getenv("AOM_ADMIN_PASSWORD"))
    ap.add_argument("--mcp-url", default="http://host.docker.internal:8200/pcl/mcp",
                    help="this backend's MCP endpoint as reachable FROM the AOM container")
    ap.add_argument("--aom-url-for-backend", default="https://host.docker.internal:8090",
                    help="AOM as reachable from the demo backend container (written to .env)")
    ap.add_argument("--backend-url", default="http://localhost:8200")
    ap.add_argument("--rotate", action="store_true", help="rotate the agent key if the agent already exists")
    ap.add_argument("--verify-tls", action="store_true")
    args = ap.parse_args()
    if not args.admin_password:
        die("Pass --admin-password (the AOM dashboard admin password you set at first login)")

    api = Api(args.aom_url, args.verify_tls)
    print(f"→ Signing in to AOM at {args.aom_url} as {args.admin_user}")
    st, body = api.call("POST", "/v1/auth/login", {"username": args.admin_user, "password": args.admin_password})
    if st != 200:
        die(f"AOM login failed ({st}): {body.get('detail')}")

    # 1. MCP server ----------------------------------------------------------
    print(f"→ Registering MCP server '{SERVER_ID}' at {args.mcp_url}")
    st, body = api.call("POST", "/v1/servers", {
        "server_id": SERVER_ID, "label": "Princess Cruises Guest Services",
        "owner": "Princess Digital Guest Experience", "mcp_url": args.mcp_url, "trust_status": "trusted",
        "default_allowed_roles": ["support_agent", "admin"],
    })
    if st == 409:
        st, body = api.call("POST", f"/v1/servers/{SERVER_ID}/reingest")
        if st != 200:
            die(f"Re-ingest failed ({st}): {body.get('detail')}")
        print(f"  already registered - re-ingested {body.get('ingested_tools')} tools")
    elif st == 200:
        if body.get("ingest_error"):
            die(f"Registered, but AOM could not reach {args.mcp_url}: {body['ingest_error']}\n"
                "  Is the demo backend running (docker compose up) and reachable from the AOM container?")
        print(f"  registered - {body.get('ingested_tools')} tools ingested into the vetted catalog")
    else:
        die(f"Server registration failed ({st}): {body.get('detail')}")

    # 2. agent identity ---------------------------------------------------------
    st, body = api.call("GET", "/v1/agents")
    if st != 200:
        die(f"Listing agents failed ({st}): {body.get('detail')}")
    body_agents = body
    existing = next((a for a in body.get("agents", []) if a.get("name") == AGENT_NAME and a.get("status") == "active"), None)
    key = None
    if existing and args.rotate:
        print(f"→ Rotating key for agent '{AGENT_NAME}' ({existing['agent_id']})")
        st, body = api.call("POST", f"/v1/agents/{existing['agent_id']}/rotate", {"revoke_immediately": False})
        if st != 200:
            die(f"Rotate failed ({st}): {body.get('detail')}")
        key = body["api_key"]
    elif existing:
        print(f"  agent '{AGENT_NAME}' already exists ({existing['agent_id']}); keeping its key (use --rotate for a new one)")
    else:
        print(f"→ Issuing agent identity '{AGENT_NAME}' (role support_agent, {len(TOOLS)} scoped tools)")
        st, body = api.call("POST", "/v1/agents", {
            "name": AGENT_NAME, "role": "support_agent", "owner": "Princess Digital Guest Experience",
            "description": "Princess Cruises mobile app concierge: personalization, RAG over the daily Adobe Real-Time CDP guest "
                           "profiles, and guest-service actions (upgrades, excursions, dining, packages, check-in).",
            "allowed_tools": [f"{SERVER_ID}::{t}" for t in TOOLS],
        })
        if st != 200:
            die(f"Agent creation failed ({st}): {body.get('detail')}")
        key = body["api_key"]
        print(f"  agent {body['agent']['agent_id']} issued")

    # 2b. the Stateroom Upgrade Agent --------------------------------------------------
    existing_up = next((a for a in body_agents.get("agents", []) if a.get("name") == UPGRADE_AGENT_NAME
                        and a.get("status") == "active"), None)
    upgrade_key = None
    if existing_up and args.rotate:
        print(f"→ Rotating key for agent '{UPGRADE_AGENT_NAME}' ({existing_up['agent_id']})")
        st, body = api.call("POST", f"/v1/agents/{existing_up['agent_id']}/rotate", {"revoke_immediately": False})
        if st != 200:
            die(f"Rotate failed ({st}): {body.get('detail')}")
        upgrade_key = body["api_key"]
    elif existing_up:
        print(f"  agent '{UPGRADE_AGENT_NAME}' already exists ({existing_up['agent_id']}); keeping its key")
    else:
        print(f"→ Issuing agent identity '{UPGRADE_AGENT_NAME}' (role support_agent, {len(UPGRADE_TOOLS)} scoped tools, Agent Memory)")
        st, body = api.call("POST", "/v1/agents", {
            "name": UPGRADE_AGENT_NAME, "role": "support_agent", "owner": "Princess Digital Guest Experience",
            "description": UPGRADE_DESCRIPTION,
            "allowed_tools": [f"{SERVER_ID}::{t}" for t in UPGRADE_TOOLS],
        })
        if st != 200:
            die(f"Agent creation failed ({st}): {body.get('detail')}")
        upgrade_key = body["api_key"]
        print(f"  agent {body['agent']['agent_id']} issued")

    # 3. approval tier ---------------------------------------------------------------
    st, body = api.call("GET", "/v1/approvals-config")
    if st == 200:
        cfg = body["config"]
        cfg["enabled"] = True
        cfg["require_for_tools"] = sorted(set(cfg.get("require_for_tools") or []) | set(APPROVAL_TOOLS))
        st, body = api.call("PUT", "/v1/approvals-config", {"config": cfg})
        print("→ Approval tier: goodwill upgrades now wait for a human" if st == 200
              else f"  ! could not update approvals ({st}): {body.get('detail')}")

    # 4. RAG application -------------------------------------------------------------
    st, body = api.call("GET", "/v1/knowledge")
    playbooks = sorted((d for d in (body.get("documents") or []) if str(d.get("title", "")).startswith("Guest Services Playbook")),
                       key=lambda d: str(d.get("created_at") or d.get("ingested_at") or d.get("title")))
    playbook_id = playbooks[-1].get("document_id") if (st == 200 and playbooks) else None
    app = rag_app_definition(playbook_id)
    print(f"→ Registering RAG application '{RAG_APP_ID}'")
    st, body = api.call("POST", "/v1/rag/apps", {"app": app, "issue_key": False})
    if st == 409:
        st, body = api.call("PUT", f"/v1/rag/apps/{RAG_APP_ID}", {"app": app})
        verb = "updated"
    else:
        verb = "registered"
    if st == 200:
        if playbook_id:
            print(f"  {verb}, scoped to playbook document {playbook_id}")
        else:
            print(f"  {verb} (disabled until the backend publishes today's playbook to the Knowledge Base;\n"
                  "  the backend enables it and scopes it to that document on its next load)")
    elif st in (404, 405):
        print("  ! this AOM build has no RAG Applications API - update AOM to see the concierge there")
    else:
        print(f"  ! RAG application registration failed ({st}): {body.get('detail')}")

    # 5. .env + reload -----------------------------------------------------------------
    updates = {"AOM_URL": args.aom_url_for_backend, "AOM_ADMIN_USERNAME": args.admin_user,
               "AOM_ADMIN_PASSWORD": args.admin_password}
    if key:
        updates["AOM_AGENT_API_KEY"] = key
    if upgrade_key:
        updates["AOM_UPGRADE_AGENT_API_KEY"] = upgrade_key
    set_env(updates)
    print(f"→ Wrote {', '.join(updates)} to {os.path.abspath(ENV_PATH)}")
    if key:
        print(f"\n  Agent API key (shown once by AOM, now in .env): {key[:10]}…")
    print("\nNext: docker compose up -d --build backend   (rebuilds and recreates the backend with the new .env;\n"
          "      it publishes the Knowledge Base to AOM and scopes the RAG application to today's playbook)")


if __name__ == "__main__":
    main()
