from unittest.mock import MagicMock

import pytest

from zrb.config.web_auth_config import WebAuthConfig
from zrb.runner.web_schema.user import User
from zrb.runner.web_util.token import generate_tokens_by_credentials, regenerate_tokens


def test_generate_tokens_by_credentials_no_auth():
    config = WebAuthConfig(enable_auth=False)
    # When auth is disabled, it returns default user tokens regardless of credentials
    tokens = generate_tokens_by_credentials(config, "any", "any")
    assert tokens is not None
    assert tokens.access_token != ""


def test_generate_tokens_by_credentials_with_auth_fail():
    config = WebAuthConfig(enable_auth=True)
    # No users registered, so it should fail
    tokens = generate_tokens_by_credentials(config, "user", "pass")
    assert tokens is None


def test_regenerate_tokens_fail_invalid():
    config = WebAuthConfig()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        regenerate_tokens(config, "invalid-token")
    assert excinfo.value.status_code == 401
