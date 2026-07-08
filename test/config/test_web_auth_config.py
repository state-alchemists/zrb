import pytest

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.runner.web_schema.user import User


def test_web_auth_config_defaults():
    config = WebAuthConfig()
    assert config.secret_key == CFG.WEB_SECRET_KEY
    assert (
        config.access_token_expire_minutes == CFG.WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    assert (
        config.refresh_token_expire_minutes == CFG.WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES
    )
    assert config.access_token_cookie_name == CFG.WEB_ACCESS_TOKEN_COOKIE_NAME
    assert config.refresh_token_cookie_name == CFG.WEB_REFRESH_TOKEN_COOKIE_NAME
    assert config.enable_auth == CFG.WEB_AUTH_ENABLED
    assert config.super_admin_username == CFG.WEB_SUPER_ADMIN_USERNAME
    assert config.super_admin_password == CFG.WEB_SUPER_ADMIN_PASSWORD
    assert config.guest_username == CFG.WEB_GUEST_USERNAME
    assert config.guest_accessible_tasks == []


def test_web_auth_config_setters():
    config = WebAuthConfig()

    config.secret_key = "new_secret"
    assert config.secret_key == "new_secret"

    config.access_token_expire_minutes = 100
    assert config.access_token_expire_minutes == 100

    config.refresh_token_expire_minutes = 200
    assert config.refresh_token_expire_minutes == 200

    config.access_token_cookie_name = "new_access_cookie"
    assert config.access_token_cookie_name == "new_access_cookie"

    config.refresh_token_cookie_name = "new_refresh_cookie"
    assert config.refresh_token_cookie_name == "new_refresh_cookie"

    config.enable_auth = True
    assert config.enable_auth is True

    config.super_admin_username = "new_admin"
    assert config.super_admin_username == "new_admin"

    config.super_admin_password = "new_password"
    assert config.super_admin_password == "new_password"

    config.guest_username = "new_guest"
    assert config.guest_username == "new_guest"

    config.guest_accessible_tasks = ["task1", "task2"]
    assert config.guest_accessible_tasks == ["task1", "task2"]


def test_web_auth_config_find_user_by_username_callback():
    config = WebAuthConfig()

    def mock_find_user(username: str):
        return None

    config.find_user_by_username_callback = mock_find_user
    assert config.find_user_by_username_callback == mock_find_user


def test_web_auth_config_secure_cookies_default():
    # No override -> falls back to CFG (covers line 104)
    config = WebAuthConfig()
    assert config.secure_cookies == CFG.WEB_ENABLE_SECURE_COOKIES


def test_web_auth_config_secure_cookies_setter():
    # Setter stores the value, getter returns it (covers lines 102-103, 108)
    config = WebAuthConfig()
    config.secure_cookies = True
    assert config.secure_cookies is True
    config.secure_cookies = False
    assert config.secure_cookies is False


def test_web_auth_config_user_list_without_auth():
    # enable_auth False -> user_list is just the default guest user (covers line 187)
    config = WebAuthConfig(enable_auth=False)
    users = config.user_list
    assert len(users) == 1
    assert users[0].is_guest is True


def test_web_auth_config_append_user():
    # With auth enabled, user_list includes appended users plus admin/default
    # (covers lines 162, 178, 188, 191-196, 198)
    config = WebAuthConfig(enable_auth=True)
    new_user = User(username="alice", password="secret")
    config.append_user(new_user)
    usernames = [u.username for u in config.user_list]
    assert "alice" in usernames


def test_web_auth_config_append_duplicate_user_raises():
    # Appending an existing username raises (covers line 197)
    config = WebAuthConfig(enable_auth=True)
    config.append_user(User(username="bob", password="secret"))
    with pytest.raises(ValueError):
        config.append_user(User(username="bob", password="other"))


def test_web_auth_config_find_user_by_username_uses_callback():
    # Callback returns a user directly (covers line 203)
    expected = User(username="carol", password="secret")

    def find(username: str):
        return expected if username == "carol" else None

    config = WebAuthConfig(find_user_by_username=find)
    assert config.find_user_by_username("carol") is expected


def test_web_auth_config_find_user_by_username_falls_back_to_list():
    # Callback returns None -> falls back to user_list lookup
    config = WebAuthConfig(enable_auth=True, find_user_by_username=lambda u: None)
    config.append_user(User(username="dave", password="secret"))
    found = config.find_user_by_username("dave")
    assert found is not None
    assert found.username == "dave"
