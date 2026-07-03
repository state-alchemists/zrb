"""Tests for web_util/cookie.py."""

from unittest.mock import MagicMock

from zrb.runner.web_schema.token import Token
from zrb.runner.web_util import cookie as cookie_module


class TestSetAuthCookie:
    """Tests for set_auth_cookie function."""

    def test_set_auth_cookie(self):
        """Test that set_auth_cookie sets cookies correctly."""
        mock_config = MagicMock()
        mock_config.access_token_expire_minutes = 30
        mock_config.refresh_token_expire_minutes = 60
        mock_config.access_token_cookie_name = "access_token"
        mock_config.refresh_token_cookie_name = "refresh_token"
        mock_config.secure_cookies = True

        mock_response = MagicMock()
        mock_token = Token(
            access_token="test_access",
            refresh_token="test_refresh",
            token_type="Bearer",
        )

        cookie_module.set_auth_cookie(mock_config, mock_response, mock_token)

        assert mock_response.set_cookie.call_count == 2

        access_call = mock_response.set_cookie.call_args_list[0]
        assert access_call.kwargs["key"] == "access_token"
        assert access_call.kwargs["value"] == "test_access"
        assert access_call.kwargs["httponly"] is True
        assert access_call.kwargs["secure"] is True

        refresh_call = mock_response.set_cookie.call_args_list[1]
        assert refresh_call.kwargs["key"] == "refresh_token"
        assert refresh_call.kwargs["value"] == "test_refresh"
        assert refresh_call.kwargs["httponly"] is True
        assert refresh_call.kwargs["secure"] is True

    def test_set_auth_cookie_insecure_for_plain_http_deployments(self):
        """secure follows config so cookie auth works on plain-HTTP hosts."""
        mock_config = MagicMock()
        mock_config.access_token_expire_minutes = 30
        mock_config.refresh_token_expire_minutes = 60
        mock_config.access_token_cookie_name = "access_token"
        mock_config.refresh_token_cookie_name = "refresh_token"
        mock_config.secure_cookies = False

        mock_response = MagicMock()
        mock_token = Token(
            access_token="test_access",
            refresh_token="test_refresh",
            token_type="Bearer",
        )

        cookie_module.set_auth_cookie(mock_config, mock_response, mock_token)

        for call in mock_response.set_cookie.call_args_list:
            assert call.kwargs["secure"] is False
