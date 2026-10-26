import os
import tempfile

import pytest
from fastapi.testclient import TestClient

_test_directory = tempfile.TemporaryDirectory(prefix="setu-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_directory.name}/test.db"
os.environ["DEMO_AUTO_SEED"] = "false"
os.environ["APP_ENV"] = "development"
os.environ["DEMO_MODE"] = "true"

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_client(client):
    login = client.post(
        "/api/v1/auth/login", json={"email": "dr.anitha@demo.setu", "password": "demo123"}
    )
    assert login.status_code == 200
    response = client.post("/api/v1/demo/seed", json={"scenario": "default"})
    assert response.status_code == 200
    return client
