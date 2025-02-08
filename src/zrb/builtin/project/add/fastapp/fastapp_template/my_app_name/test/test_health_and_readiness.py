from fastapi.testclient import TestClient
from my_app_name.main import app


def test_get_health():
    client = TestClient(app, base_url="http://localhost")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"message": "ok"}


def test_head_health():
    client = TestClient(app, base_url="http://localhost")
    response = client.head("/health")
    assert response.status_code == 200


def test_get_readiness():
    client = TestClient(app, base_url="http://localhost")
    response = client.get("/readiness")
    assert response.status_code == 200
    assert response.json() == {"message": "ok"}


def test_head_readiness():
    client = TestClient(app, base_url="http://localhost")
    response = client.head("/readiness")
    assert response.status_code == 200
