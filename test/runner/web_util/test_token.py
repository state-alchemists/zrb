"""Tests for web_util/token.py."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest

from zrb.runner.web_util.token import (
    generate_tokens_by_credentials,
    regenerate_tokens,
)


@pytest.fixture
def mock_web_auth_config():
    """Create a mock WebAuthConfig for testing."""
    config = MagicMock()
    config.enable_auth = True
    config.secret_key = "test-secret-key-for-jwt-token-generation"
    config.access_token_expire_minutes = 30
    config.refresh_token_expire_minutes = 1440  # 24 hours

    # Create a test user
    test_user = MagicMock(username="testuser")
    test_user.is_password_match = MagicMock(return_value=True)

    config.default_user = test_user
    config.find_user_by_username = MagicMock(return_value=test_user)
    return config


class TestGenerateTokensByCredentials:
    """Tests for generate_tokens_by_credentials function."""

    def test_generate_tokens_no_auth_returns_default_user(self, mock_web_auth_config):
        """Test token generation when authentication is disabled."""
        mock_web_auth_config.enable_auth = False
        default_user = MagicMock(username="default_user")
        mock_web_auth_config.default_user = default_user

        result = generate_tokens_by_credentials(
            mock_web_auth_config, "any_user", "any_password"
        )

        assert result is not None
        assert result.token_type == "bearer"
        assert result.access_token is not None
        assert result.refresh_token is not None

    def test_generate_tokens_with_valid_credentials(self, mock_web_auth_config):
        """Test token generation with valid credentials."""
        test_user = MagicMock(username="testuser")
        test_user.is_password_match = MagicMock(return_value=True)
        mock_web_auth_config.find_user_by_username = MagicMock(return_value=test_user)

        result = generate_tokens_by_credentials(
            mock_web_auth_config, "testuser", "password"
        )

        assert result is not None
        assert result.token_type == "bearer"
        assert result.access_token is not None
        assert result.refresh_token is not None

    def test_generate_tokens_user_not_found(self, mock_web_auth_config):
        """Test token generation when user is not found."""
        mock_web_auth_config.find_user_by_username = MagicMock(return_value=None)

        result = generate_tokens_by_credentials(
            mock_web_auth_config, "nonexistent", "password"
        )

        assert result is None

    def test_generate_tokens_wrong_password(self, mock_web_auth_config):
        """Test token generation with wrong password."""
        test_user = MagicMock(username="testuser")
        test_user.is_password_match = MagicMock(return_value=False)
        mock_web_auth_config.find_user_by_username = MagicMock(return_value=test_user)

        result = generate_tokens_by_credentials(
            mock_web_auth_config, "testuser", "wrongpassword"
        )

        assert result is None

    def test_generate_tokens_creates_valid_jwt(self, mock_web_auth_config):
        """Test that generated tokens are valid JWTs."""
        mock_web_auth_config.enable_auth = False
        mock_web_auth_config.default_user = MagicMock(username="default_user")

        result = generate_tokens_by_credentials(
            mock_web_auth_config, "user", "password"
        )

        # Decode and verify access token
        access_payload = jwt.decode(
            result.access_token,
            mock_web_auth_config.secret_key,
            algorithms=["HS256"],
        )
        assert access_payload["sub"] == "default_user"
        assert access_payload["type"] == "access"

        # Decode and verify refresh token
        refresh_payload = jwt.decode(
            result.refresh_token,
            mock_web_auth_config.secret_key,
            algorithms=["HS256"],
        )
        assert refresh_payload["sub"] == "default_user"
        assert refresh_payload["type"] == "refresh"


class TestRegenerateTokens:
    """Tests for regenerate_tokens function."""

    def test_regenerate_tokens_success(self, mock_web_auth_config):
        """Test successful token regeneration."""
        # Create a valid refresh token
        refresh_token = jwt.encode(
            {
                "sub": "testuser",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "type": "refresh",
            },
            mock_web_auth_config.secret_key,
            algorithm="HS256",
        )

        result = regenerate_tokens(mock_web_auth_config, refresh_token)

        assert result is not None
        assert result.token_type == "bearer"
        assert result.access_token is not None
        assert result.refresh_token is not None

        # Verify new tokens have correct subject
        access_payload = jwt.decode(
            result.access_token,
            mock_web_auth_config.secret_key,
            algorithms=["HS256"],
        )
        assert access_payload["sub"] == "testuser"

    def test_regenerate_tokens_expired_token(self, mock_web_auth_config):
        """Test regeneration with expired refresh token."""
        from fastapi import HTTPException

        # Create an expired refresh token
        expired_token = jwt.encode(
            {
                "sub": "testuser",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "type": "refresh",
            },
            mock_web_auth_config.secret_key,
            algorithm="HS256",
        )

        with pytest.raises(HTTPException) as excinfo:
            regenerate_tokens(mock_web_auth_config, expired_token)

        assert excinfo.value.status_code == 401
        assert "expired" in excinfo.value.detail.lower()

    def test_regenerate_tokens_invalid_token(self, mock_web_auth_config):
        """Test regeneration with invalid JWT token."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            regenerate_tokens(mock_web_auth_config, "invalid.token.here")

        assert excinfo.value.status_code == 401
        assert "invalid" in excinfo.value.detail.lower()

    def test_regenerate_tokens_wrong_token_type(self, mock_web_auth_config):
        """Test regeneration with access token instead of refresh token."""
        from fastapi import HTTPException

        # Create an access token instead of refresh token
        access_token = jwt.encode(
            {
                "sub": "testuser",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "type": "access",
            },
            mock_web_auth_config.secret_key,
            algorithm="HS256",
        )

        with pytest.raises(HTTPException) as excinfo:
            regenerate_tokens(mock_web_auth_config, access_token)

        assert excinfo.value.status_code == 401
        assert "token type" in excinfo.value.detail.lower()

    def test_regenerate_tokens_user_not_found(self, mock_web_auth_config):
        """Test regeneration when user no longer exists."""
        from fastapi import HTTPException

        refresh_token = jwt.encode(
            {
                "sub": "deleted_user",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "type": "refresh",
            },
            mock_web_auth_config.secret_key,
            algorithm="HS256",
        )

        mock_web_auth_config.find_user_by_username = MagicMock(return_value=None)

        with pytest.raises(HTTPException) as excinfo:
            regenerate_tokens(mock_web_auth_config, refresh_token)

        assert excinfo.value.status_code == 401
        assert "user" in excinfo.value.detail.lower()

    def test_regenerate_tokens_missing_subject(self, mock_web_auth_config):
        """Test regeneration with token missing subject."""
        from fastapi import HTTPException

        # Token without 'sub' field
        token_no_sub = jwt.encode(
            {
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "type": "refresh",
            },
            mock_web_auth_config.secret_key,
            algorithm="HS256",
        )

        with pytest.raises(HTTPException) as excinfo:
            regenerate_tokens(mock_web_auth_config, token_no_sub)

        # jwt.decode will raise InvalidTokenError due to missing required 'sub'
        assert excinfo.value.status_code == 401
