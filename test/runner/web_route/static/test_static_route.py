from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zrb.config.web_auth_config import WebAuthConfig
from zrb.runner.web_route.static.static_route import serve_static_resources


def _client(enable_auth: bool) -> TestClient:
    app = FastAPI()
    web_auth_config = MagicMock(spec=WebAuthConfig)
    web_auth_config.enable_auth = enable_auth
    web_auth_config.access_token_expire_minutes = 30
    serve_static_resources(app, web_auth_config)
    return TestClient(app)


@pytest.mark.parametrize("enable_auth", [True, False])
def test_refresh_token_js_is_always_served(enable_auth: bool):
    """The URL must keep answering 200 — a cached page still requests it."""
    response = _client(enable_auth).get("/refresh-token.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")


def test_refresh_token_js_is_inert_when_auth_is_disabled():
    """No token to refresh, so the script must not POST.

    Regression: it fired one unconditional POST per page load, and with auth off
    that could only ever 401 — every page view logged what reads as a real auth
    failure.
    """
    body = _client(enable_auth=False).get("/refresh-token.js").text

    assert "/api/v1/refresh-token" not in body
    assert "fetch(" not in body


def test_refresh_token_js_still_refreshes_when_auth_is_enabled():
    body = _client(enable_auth=True).get("/refresh-token.js").text

    assert "/api/v1/refresh-token" in body
    assert "setInterval" in body
