"""Adobe Experience Platform clients: Real-Time CDP (guest context) and AEM
(content). See adobe/rtcdp/README.md and adobe/aem/README.md.

Two sources, two modes each:

* **Real-Time CDP Profile Access API** - the guest's *current* unified
  profile: audience memberships and Customer AI propensity scores. Called
  when the concierge assembles a guest's context (an AOM Context Cache
  miss); the round trip is the `source_latency_ms` the Context Cache
  records. With IMS credentials configured it calls
  `platform.adobe.io/data/core/ups/access/entities`; without them (`mock`)
  it answers from the profile the daily export loaded into Couchbase, with
  the latency such a call has in practice, so the demo shows the same
  cache economics.
* **AEM Content Fragments (GraphQL)** - the Guest Services Playbook
  entries. With `AEM_GRAPHQL_ENDPOINT` configured it runs the persisted
  query; without it the bundled fragments in knowledge.FAQ are served in the
  same shape.

The daily batch (dataset export -> loader.py) is the third Adobe touchpoint
and needs no client here: the files simply land in RTCDP_EXPORT_DIR.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time

import httpx

from . import config

log = logging.getLogger("pcl.adobe")

IMS_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
PROFILE_ACCESS_URL = "https://platform.adobe.io/data/core/ups/access/entities"
PROFILE_SCOPES = "openid,AdobeID,read_organizations,additional_info.projectedProductContext,session"

STATUS: dict = {"rtcdp": {"mode": "mock", "calls": 0, "errors": 0, "last_latency_ms": None},
                "aem": {"mode": "mock", "calls": 0, "errors": 0}}


class AdobeError(Exception):
    pass


class _IMS:
    """OAuth server-to-server token for the Developer Console project."""

    def __init__(self):
        self._token = None
        self._exp = 0.0

    @property
    def configured(self) -> bool:
        return bool(config.ADOBE_IMS_CLIENT_ID and config.ADOBE_IMS_CLIENT_SECRET and config.ADOBE_IMS_ORG_ID)

    async def token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._exp - 60:
            return self._token
        r = await client.post(IMS_TOKEN_URL, data={
            "grant_type": "client_credentials", "client_id": config.ADOBE_IMS_CLIENT_ID,
            "client_secret": config.ADOBE_IMS_CLIENT_SECRET, "scope": config.ADOBE_IMS_SCOPES or PROFILE_SCOPES})
        if r.status_code >= 400:
            raise AdobeError(f"IMS token: HTTP {r.status_code} {r.text[:200]}")
        data = r.json()
        self._token, self._exp = data["access_token"], time.time() + int(data.get("expires_in", 3600))
        return self._token

    def headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "x-api-key": config.ADOBE_IMS_CLIENT_ID,
                "x-gw-ims-org-id": config.ADOBE_IMS_ORG_ID, "x-sandbox-name": config.ADOBE_SANDBOX}


_ims = _IMS()
_client = httpx.AsyncClient(timeout=config.ADOBE_TIMEOUT_SECONDS)


# --------------------------------------------------------------------------
# Real-Time CDP: the guest's current profile
# --------------------------------------------------------------------------
def _mock_profile_view(profile: dict) -> dict:
    """What the Profile Access API returns for this guest, from the exported
    profile: identity, realized audiences, Customer AI scores."""
    s = profile.get("ml_scores") or {}
    return {
        "identity": profile.get("identity") or {"guest_id": profile["guest_id"], "namespace": config.ADOBE_RTCDP_IDENTITY_NAMESPACE},
        "segmentMembership": [{"id": a["id"], "name": a["name"], "status": a.get("status", "realized")}
                              for a in (profile.get("audiences") or [])],
        "propensity": {k: v for k, v in s.items() if k.endswith("_propensity") or k in ("price_sensitivity", "segment",
                                                                                          "next_best_action", "model_version")},
        "loyalty": profile.get("loyalty"),
        "consent": profile.get("consent"),
        "profile_updated_at": f"{profile.get('export_date')}T05:00:00Z",
    }


async def profile_view(guest_id: str, profile: dict | None) -> dict:
    """The guest's current Real-Time CDP profile view + how long it took.
    `profile` is the exported profile from Couchbase (used by the mock, and
    as the fallback if the live call fails)."""
    t0 = time.perf_counter()
    st = STATUS["rtcdp"]
    st["calls"] += 1
    if _ims.configured:
        st["mode"] = "live"
        try:
            token = await _ims.token(_client)
            r = await _client.get(PROFILE_ACCESS_URL, headers=_ims.headers(token), params={
                "schema.name": "_xdm.context.profile", "entityId": guest_id,
                "entityIdNS": config.ADOBE_RTCDP_IDENTITY_NAMESPACE,
                "fields": "segmentMembership,_princess.propensity,_princess.loyalty,_princess.identity,consents"})
            if r.status_code >= 400:
                raise AdobeError(f"Profile Access: HTTP {r.status_code} {r.text[:200]}")
            entity = next(iter(r.json().values()), {}).get("entity", {})
            view = {
                "identity": entity.get("_princess", {}).get("identity") or {"guest_id": guest_id},
                "segmentMembership": [{"id": k, "name": v.get("name", k), "status": v.get("status", "realized")}
                                      for ns in (entity.get("segmentMembership") or {}).values() for k, v in ns.items()],
                "propensity": entity.get("_princess", {}).get("propensity") or {},
                "loyalty": entity.get("_princess", {}).get("loyalty") or (profile or {}).get("loyalty"),
                "consent": entity.get("consents"),
                "profile_updated_at": entity.get("timestamp"),
            }
        except (AdobeError, httpx.HTTPError) as exc:
            st["errors"] += 1
            log.warning("Real-Time CDP profile lookup failed (%s); using the exported profile", exc)
            view = _mock_profile_view(profile) if profile else {"identity": {"guest_id": guest_id}, "segmentMembership": [], "propensity": {}}
            view["fallback"] = str(exc)[:120]
    else:
        st["mode"] = "mock"
        # The Profile Access API answers in roughly 120-350 ms from the edge;
        # that latency is the point of caching the assembled context.
        await asyncio.sleep(random.uniform(config.ADOBE_MOCK_LATENCY_MS[0], config.ADOBE_MOCK_LATENCY_MS[1]) / 1000)
        view = _mock_profile_view(profile) if profile else {"identity": {"guest_id": guest_id}, "segmentMembership": [], "propensity": {}}
    view["source"] = "adobe-rtcdp"
    view["mode"] = st["mode"]
    view["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    st["last_latency_ms"] = view["latency_ms"]
    return view


def audiences_text(view: dict) -> str:
    names = [m["name"] for m in view.get("segmentMembership", []) if m.get("status", "realized") == "realized"]
    return ", ".join(names) if names else "no audience memberships"


# --------------------------------------------------------------------------
# AEM: Guest Services Playbook content fragments
# --------------------------------------------------------------------------
async def playbook_entries(today: str) -> tuple[list[dict], str]:
    """The playbook's content fragments: [{section, question, answer, keywords}], mode."""
    from . import knowledge  # late import: knowledge renders with these entries
    st = STATUS["aem"]
    st["calls"] += 1
    if config.AEM_GRAPHQL_ENDPOINT:
        st["mode"] = "live"
        try:
            headers = {"Authorization": f"Bearer {config.AEM_TOKEN}"} if config.AEM_TOKEN else {}
            r = await _client.get(f"{config.AEM_GRAPHQL_ENDPOINT.rstrip('/')}/graphql/execute.json/princess/guest-services-playbook",
                                  params={"today": today}, headers=headers)
            if r.status_code >= 400:
                raise AdobeError(f"AEM GraphQL: HTTP {r.status_code} {r.text[:200]}")
            items = r.json().get("data", {}).get("guestServicesPlaybookEntryList", {}).get("items", [])
            entries = [{"section": i.get("section"), "q": i.get("question"), "a": (i.get("answer") or {}).get("plaintext", ""),
                        "keywords": i.get("keywords") or [], "path": i.get("_path")} for i in items]
            if entries:
                return entries, "live"
        except (AdobeError, httpx.HTTPError) as exc:
            st["errors"] += 1
            log.warning("AEM playbook fetch failed (%s); using the bundled fragments", exc)
    st["mode"] = "mock"
    return [dict(f) for f in knowledge.FAQ], "mock"
