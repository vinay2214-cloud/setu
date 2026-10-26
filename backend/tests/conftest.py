import pytest
from fastapi.testclient import TestClient

from app.main import app


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
