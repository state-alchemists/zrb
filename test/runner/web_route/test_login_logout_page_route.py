from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zrb.config.web_auth_config import WebAuthConfig
from zrb.runner.web_route.login_page.login_page_route import serve_login_page
from zrb.runner.web_route.logout_page.logout_page_route import serve_logout_page


@pytest.fixture
def app_deps():
    app = FastAPI()
    root_group = MagicMock()
    web_auth_config = MagicMock(spec=WebAuthConfig)
    web_auth_config.access_token_cookie_name = "access_token"

    serve_login_page(app, root_group, web_auth_config)
    serve_logout_page(app, root_group, web_auth_config)
    client = TestClient(app)
    return client, web_auth_config


def test_login_page_route(app_deps):
    client, web_auth_config = app_deps

    # Mock jinja template rendering
    mock_template = MagicMock()
    mock_template.render.return_value = "<html>login</html>"

    mock_env = MagicMock()
    mock_env.get_template.return_value = mock_template

    with patch(
        "zrb.runner.web_route.login_page.login_page_route.get_jinja_env",
        return_value=mock_env,
    ):
        response = client.get("/login")
        assert response.status_code == 200
        assert "login" in response.text


def test_logout_page_route(app_deps):
    client, web_auth_config = app_deps

    mock_template = MagicMock()
    mock_template.render.return_value = "<html>logout</html>"

    mock_env = MagicMock()
    mock_env.get_template.return_value = mock_template

    mock_user = MagicMock()
    mock_user.username = "testuser"

    with patch(
        "zrb.runner.web_route.logout_page.logout_page_route.get_jinja_env",
        return_value=mock_env,
    ), patch(
        "zrb.runner.web_route.logout_page.logout_page_route.get_user_from_request",
        new_callable=AsyncMock,
        return_value=mock_user,
    ):
        response = client.get("/logout")
        assert response.status_code == 200
        assert "logout" in response.text
