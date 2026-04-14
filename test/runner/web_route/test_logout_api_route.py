"""Tests for logout_api_route.py."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zrb.config.web_auth_config import WebAuthConfig
from zrb.runner.web_route.logout_api_route import serve_logout_api


@pytest.fixture
def web_auth_config():
    return WebAuthConfig(
        secret_key="test-secret-key-for-testing-only-32-chars",
        access_token_expire_minutes=30,
        refresh_token_expire_minutes=10080,
    )


@pytest.fixture
def client(web_auth_config):
    app = FastAPI()
    serve_logout_api(app, web_auth_config)
    return TestClient(app)


class TestLogoutAPI:
    """Test serve_logout_api endpoint."""

    def test_logout_get(self, client):
        """GET /api/v1/logout returns success message (line 18)."""
        response = client.get("/api/v1/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logout successful"

    def test_logout_post(self, client):
        """POST /api/v1/logout returns success message."""
        response = client.post("/api/v1/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logout successful"
