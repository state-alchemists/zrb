"""Tests for web_util/user.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from zrb.runner.web_util import user as user_module


@pytest.fixture
def mock_web_auth_config():
    config = MagicMock()
    config.enable_auth = True
    config.secret_key = "test-secret-key"
    config.access_token_cookie_name = "access_token"
    config.default_user = MagicMock(username="default_user")

    # Create a test user
    test_user = MagicMock(username="testuser")
    test_user.is_password_match = MagicMock(return_value=True)

    config.find_user_by_username = MagicMock(return_value=test_user)
    return config


class TestGetUserByCredentials:
    """Tests for get_user_by_credentials function."""

    def test_get_user_by_credentials_success(self, mock_web_auth_config):
        test_user = MagicMock(username="testuser")
        test_user.is_password_match = MagicMock(return_value=True)
        mock_web_auth_config.find_user_by_username = MagicMock(return_value=test_user)

        result = user_module.get_user_by_credentials(
            mock_web_auth_config, "testuser", "password"
        )
        assert result == test_user

    def test_get_user_by_credentials_user_not_found(self, mock_web_auth_config):
        mock_web_auth_config.find_user_by_username = MagicMock(return_value=None)

        result = user_module.get_user_by_credentials(
            mock_web_auth_config, "nonexistent", "password"
        )
        assert result is None

    def test_get_user_by_credentials_wrong_password(self, mock_web_auth_config):
        test_user = MagicMock(username="testuser")
        test_user.is_password_match = MagicMock(return_value=False)
        mock_web_auth_config.find_user_by_username = MagicMock(return_value=test_user)

        result = user_module.get_user_by_credentials(
            mock_web_auth_config, "testuser", "wrongpassword"
        )
        assert result is None


class TestGetUserFromRequest:
    """Tests for get_user_from_request function."""

    @pytest.mark.asyncio
    async def test_get_user_from_request_no_auth(self, mock_web_auth_config):
        mock_web_auth_config.enable_auth = False
        request = MagicMock()
        result = await user_module.get_user_from_request(mock_web_auth_config, request)
        assert result == mock_web_auth_config.default_user

    @pytest.mark.asyncio
    async def test_get_user_from_request_with_valid_bearer_token(
        self, mock_web_auth_config
    ):
        mock_web_auth_config.enable_auth = True
        token = jwt.encode(
            {"sub": "testuser", "exp": 9999999999},
            mock_web_auth_config.secret_key,
            algorithm="HS256",
        )
        test_user = MagicMock(username="testuser")
        mock_web_auth_config.find_user_by_username = MagicMock(return_value=test_user)
        request = MagicMock()

        async def mock_get_bearer_token(request):
            return token

        with patch("fastapi.security.OAuth2PasswordBearer") as mock_oauth:
            mock_oauth.return_value = mock_get_bearer_token
            result = await user_module.get_user_from_request(
                mock_web_auth_config, request
            )
            assert result == test_user

    @pytest.mark.asyncio
    async def test_get_user_from_request_with_invalid_bearer_token(
        self, mock_web_auth_config
    ):
        mock_web_auth_config.enable_auth = True
        request = MagicMock()
        request.cookies = {}

        async def mock_get_bearer_token(request):
            return "invalid-token"

        with patch("fastapi.security.OAuth2PasswordBearer") as mock_oauth:
            mock_oauth.return_value = mock_get_bearer_token
            result = await user_module.get_user_from_request(
                mock_web_auth_config, request
            )
            assert result == mock_web_auth_config.default_user

    @pytest.mark.asyncio
    async def test_get_user_from_request_with_valid_cookie(self, mock_web_auth_config):
        mock_web_auth_config.enable_auth = True
        token = jwt.encode(
            {"sub": "testuser", "exp": 9999999999},
            mock_web_auth_config.secret_key,
            algorithm="HS256",
        )
        test_user = MagicMock(username="testuser")
        mock_web_auth_config.find_user_by_username = MagicMock(return_value=test_user)
        request = MagicMock()
        request.cookies = {mock_web_auth_config.access_token_cookie_name: token}

        async def mock_get_bearer_token(request):
            return None

        with patch("fastapi.security.OAuth2PasswordBearer") as mock_oauth:
            mock_oauth.return_value = mock_get_bearer_token
            result = await user_module.get_user_from_request(
                mock_web_auth_config, request
            )
            assert result == test_user

    @pytest.mark.asyncio
    async def test_get_user_from_request_no_token_returns_default(
        self, mock_web_auth_config
    ):
        mock_web_auth_config.enable_auth = True
        request = MagicMock()
        request.cookies = {}

        async def mock_get_bearer_token(request):
            return None

        with patch("fastapi.security.OAuth2PasswordBearer") as mock_oauth:
            mock_oauth.return_value = mock_get_bearer_token
            result = await user_module.get_user_from_request(
                mock_web_auth_config, request
            )
            assert result == mock_web_auth_config.default_user
