"""Shared fixture: the demo backend in memory mode (no Couchbase, no AOM),
loaded from a small generated Adobe Real-Time CDP export. One instance per test session."""
import os
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    dump = tmp_path_factory.mktemp("export")
    subprocess.run([sys.executable, os.path.join(ROOT, "adobe", "generate_mock_export.py"),
                    "--export-date", "2026-10-09", "--target-mb", "3", "--out", str(dump)], check=True,
                   capture_output=True)
    os.environ.update(STORE_DRIVER="memory", RTCDP_EXPORT_DIR=str(dump), AOM_URL="", SG_ADMIN_URL="", ADOBE_MOCK_LATENCY_MS="1,2")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        for _ in range(50):
            if c.get("/api/health").json()["load"] == "loaded":
                break
            time.sleep(0.1)
        yield c


