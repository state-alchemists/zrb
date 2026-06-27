from zrb.config.config import Config


def test_web_css_path(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_CSS_PATH", "path1:path2")
    config = Config()
    assert config.WEB_CSS_PATH == ["path1", "path2"]


def test_web_css_path_empty(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_CSS_PATH", "")
    config = Config()
    assert config.WEB_CSS_PATH == []


def test_web_js_path(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_JS_PATH", "path1:path2")
    config = Config()
    assert config.WEB_JS_PATH == ["path1", "path2"]


def test_web_js_path_empty(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_JS_PATH", "")
    config = Config()
    assert config.WEB_JS_PATH == []


def test_web_favicon_path(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_FAVICON_PATH", "/my-favicon.ico")
    config = Config()
    assert config.WEB_FAVICON_PATH == "/my-favicon.ico"


def test_web_color(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_COLOR", "blue")
    config = Config()
    assert config.WEB_COLOR == "blue"


def test_web_http_port(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_HTTP_PORT", "8080")
    config = Config()
    assert config.WEB_HTTP_PORT == 8080


def test_web_guest_username(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_GUEST_USERNAME", "guest")
    config = Config()
    assert config.WEB_GUEST_USERNAME == "guest"


def test_web_super_admin_username(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_SUPER_ADMIN_USERNAME", "superadmin")
    config = Config()
    assert config.WEB_SUPER_ADMIN_USERNAME == "superadmin"


def test_web_super_admin_password(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_SUPER_ADMIN_PASSWORD", "superpassword")
    config = Config()
    assert config.WEB_SUPER_ADMIN_PASSWORD == "superpassword"


def test_web_access_token_cookie_name(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME", "my_access_token")
    config = Config()
    assert config.WEB_ACCESS_TOKEN_COOKIE_NAME == "my_access_token"


def test_web_refresh_token_cookie_name(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME", "my_refresh_token")
    config = Config()
    assert config.WEB_REFRESH_TOKEN_COOKIE_NAME == "my_refresh_token"


def test_web_secret_key(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_SECRET_KEY", "my-secret")
    config = Config()
    assert config.WEB_SECRET_KEY == "my-secret"


def test_web_auth_enabled(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_AUTH_ENABLED", "1")
    config = Config()
    assert config.WEB_AUTH_ENABLED


def test_web_auth_access_token_expire_minutes(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    config = Config()
    assert config.WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES == 60


def test_web_auth_refresh_token_expire_minutes(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES", "120")
    config = Config()
    assert config.WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES == 120


def test_web_title(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_TITLE", "My Zrb")
    config = Config()
    assert config.WEB_TITLE == "My Zrb"


def test_web_jargon(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_JARGON", "My Powerhouse")
    config = Config()
    assert config.WEB_JARGON == "My Powerhouse"


def test_web_homepage_intro(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_HOMEPAGE_INTRO", "Hello Zrb")
    config = Config()
    assert config.WEB_HOMEPAGE_INTRO == "Hello Zrb"
