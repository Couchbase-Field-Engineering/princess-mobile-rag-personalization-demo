# Adobe Real-Time CDP: where the guest context comes from

Princess's guest context lives in Adobe Experience Platform. Real-Time CDP
holds the unified guest profile - identity-stitched across the booking system
(`crm_id`), the app and the web (`ecid`) - with Captain's Circle status,
preferences, sailing history, audience memberships and the propensity scores
Customer AI produces. The demo consumes it two ways:

## 1. Daily dataset export (batch) -> Couchbase

A scheduled **dataset export** of `guest_profile_personalization` to a cloud
storage destination (Azure Blob / S3 / ADLS) lands every morning as JSON
Lines, one profile per line, under `exportTime=YYYYMMDD/`:

    exportTime=20261104/
        part-00000-<uuid>-c000.json
        ...
        _SUCCESS
        _manifest.json

`dataset-export-destination.json` is the destination flow definition
(dataset, destination, schedule 05:00 ET, JSON, one file per partition).
The backend's loader (`backend/app/loader.py`) picks up each new partition,
upserts one `profiles` document per guest into Couchbase, re-ranks offers and
publishes the AOM Knowledge Base. Sync Gateway puts each guest's documents on
their phone. `adobe/generate_mock_export.py` writes a 100 MiB mock of that
export so the demo runs without an Adobe sandbox.

## 2. Profile Access API (real time) -> AOM Context Cache

When the concierge builds a guest's context (a Context Cache miss), it reads
the **current** profile from Real-Time CDP's Profile Access API - audience
memberships and scores can change during the day as the guest browses, books
or opens an email:

    GET https://platform.adobe.io/data/core/ups/access/entities
        ?schema.name=_xdm.context.profile
        &entityId=<guest_id>&entityIdNS=guestId
        &fields=segmentMembership,_princess.propensity,_princess.loyalty
    Authorization: Bearer <IMS access token>   x-api-key   x-gw-ims-org-id   x-sandbox-name

That round trip is what AOM's Context Cache saves: the assembled context is
stored with the real `source_latency_ms`, keyed by the export date and the
profile revision, so a booking or the next export invalidates it, and the
same document syncs to the phone for offline answers.

Configuration (`backend/app/config.py`, all optional - without credentials the
backend answers the same calls from the exported profile with a realistic
latency, labelled `mode: mock`):

| variable | meaning |
|---|---|
| `ADOBE_IMS_CLIENT_ID` / `ADOBE_IMS_CLIENT_SECRET` | OAuth server-to-server credential (Developer Console project) |
| `ADOBE_IMS_ORG_ID` | IMS organization id (`...@AdobeOrg`) |
| `ADOBE_SANDBOX` | AEP sandbox name (default `prod`) |
| `ADOBE_RTCDP_IDENTITY_NAMESPACE` | identity namespace of the guest id (default `guestId`) |
| `RTCDP_EXPORT_DIR` | where the daily export lands (default `data/adobe-rtcdp-export`) |
