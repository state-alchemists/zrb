from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig


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
    assert config.enable_auth == CFG.WEB_ENABLE_AUTH
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
