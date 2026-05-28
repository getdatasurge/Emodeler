"""Test setup — isolate the DB and storage to a temp dir before app import."""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="emodeler_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp/'test.db'}"
os.environ["STORAGE_DIR"] = str(_tmp / "storage")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
