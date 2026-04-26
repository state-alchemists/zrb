from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zrb.config.web_auth_config import WebAuthConfig
from zrb.runner.web_route.refresh_token_api_route import serve_refresh_token_api


@pytest.fixture
def app_deps():
    app = FastAPI()
    web_auth_config = MagicMock(spec=WebAuthConfig)
    web_auth_config.refresh_token_cookie_name = "refresh_token"

    serve_refresh_token_api(app, web_auth_config)
    client = TestClient(app)
    return client, web_auth_config


def test_refresh_token_api_from_body(app_deps):
    client, web_auth_config = app_deps

    with patch(
        "zrb.runner.web_route.refresh_token_api_route.regenerate_tokens",
        return_value={"access_token": "new", "refresh_token": "new_r"},
    ), patch("zrb.runner.web_route.refresh_token_api_route.set_auth_cookie"):

        response = client.post(
            "/api/v1/refresh-token", json={"refresh_token": "body_token"}
        )

        assert response.status_code == 200
        assert response.json() == {"access_token": "new", "refresh_token": "new_r"}


def test_refresh_token_api_from_cookie(app_deps):
    client, web_auth_config = app_deps

    with patch(
        "zrb.runner.web_route.refresh_token_api_route.regenerate_tokens",
        return_value={"access_token": "new", "refresh_token": "new_r"},
    ), patch("zrb.runner.web_route.refresh_token_api_route.set_auth_cookie"):

        # Set cookie on the client instance to avoid DeprecationWarning
        client.cookies.set("refresh_token", "cookie_token")
        response = client.post("/api/v1/refresh-token")

        assert response.status_code == 200


def test_refresh_token_api_missing(app_deps):
    client, web_auth_config = app_deps

    # Ensure no cookies from previous tests
    client.cookies.clear()
    response = client.post("/api/v1/refresh-token")

    assert response.status_code == 401
