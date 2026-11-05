# Adobe Real-Time CDP export landing folder

`exportTime=YYYYMMDD/` partitions delivered by the Real-Time CDP dataset-export
destination (adobe/rtcdp/dataset-export-destination.json), or written locally
by `adobe/generate_mock_export.py`: JSON Lines `part-*.json` files, `_SUCCESS`
and `_manifest.json`. The backend mounts this folder read-only at
`/data/adobe-rtcdp-export` and loads the newest complete partition on startup
and whenever a newer one appears.
