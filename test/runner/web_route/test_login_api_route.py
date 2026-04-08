"""Tests for login_api_route.py - Login API endpoint."""

from unittest.mock import MagicMock, patch

import pytest


class TestServeLoginAPI:
    """Test serve_login_api function."""

    def test_login_success(self):
        """Test successful login returns token."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from zrb.config.web_auth_config import WebAuthConfig
        from zrb.runner.web_route.login_api_route import serve_login_api

        app = FastAPI()
        web_auth_config = WebAuthConfig(
            secret_key="test-secret-key-for-testing-only-32-chars",
            access_token_expire_minutes=30,
            refresh_token_expire_minutes=10080,  # 7 days
        )

        serve_login_api(app, web_auth_config)
        client = TestClient(app)

        mock_token = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "bearer",
        }

        with patch(
            "zrb.runner.web_route.login_api_route.generate_tokens_by_credentials",
            return_value=mock_token,
        ) as mock_generate:
            with patch(
                "zrb.runner.web_route.login_api_route.set_auth_cookie"
            ) as mock_set_cookie:
                response = client.post(
                    "/api/v1/login",
                    data={"username": "testuser", "password": "testpass"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["access_token"] == "test-access-token"
                assert data["refresh_token"] == "test-refresh-token"
                assert data["token_type"] == "bearer"

                mock_generate.assert_called_once_with(
                    web_auth_config=web_auth_config,
                    username="testuser",
                    password="testpass",
                )
                mock_set_cookie.assert_called_once()

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 400."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from zrb.config.web_auth_config import WebAuthConfig
        from zrb.runner.web_route.login_api_route import serve_login_api

        app = FastAPI()
        web_auth_config = WebAuthConfig(
            secret_key="test-secret-key-for-testing-only-32-chars",
            access_token_expire_minutes=30,
            refresh_token_expire_minutes=10080,  # 7 days
        )

        serve_login_api(app, web_auth_config)
        client = TestClient(app)

        with patch(
            "zrb.runner.web_route.login_api_route.generate_tokens_by_credentials",
            return_value=None,
        ) as mock_generate:
            response = client.post(
                "/api/v1/login",
                data={"username": "wronguser", "password": "wrongpass"},
            )

            assert response.status_code == 400
            data = response.json()
            assert data["detail"] == "Incorrect username or password"

            mock_generate.assert_called_once_with(
                web_auth_config=web_auth_config,
                username="wronguser",
                password="wrongpass",
            )
