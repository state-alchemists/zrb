import os

from zrb.config.config import Config


class TestWebConfigSetters:
    """Test Config property setters by verifying they write to os.environ."""

    _original_env: dict[str, str] = {}

    def test_web_css_path_setter(self, monkeypatch):
        config = Config()
        config.WEB_CSS_PATH = ["css1", "css2"]
        assert os.environ["ZRB_WEB_CSS_PATH"] == "css1:css2"

    def test_web_js_path_setter(self, monkeypatch):
        config = Config()
        config.WEB_JS_PATH = ["js1", "js2"]
        assert os.environ["ZRB_WEB_JS_PATH"] == "js1:js2"

    def test_web_favicon_path_setter(self, monkeypatch):
        config = Config()
        config.WEB_FAVICON_PATH = "/favicon.ico"
        assert os.environ["ZRB_WEB_FAVICON_PATH"] == "/favicon.ico"

    def test_web_color_setter(self, monkeypatch):
        config = Config()
        config.WEB_COLOR = "red"
        assert os.environ["ZRB_WEB_COLOR"] == "red"

    def test_web_http_port_setter(self, monkeypatch):
        config = Config()
        config.WEB_HTTP_PORT = 1234
        assert os.environ["ZRB_WEB_HTTP_PORT"] == "1234"

    def test_web_guest_username_setter(self, monkeypatch):
        config = Config()
        config.WEB_GUEST_USERNAME = "guestuser"
        assert os.environ["ZRB_WEB_GUEST_USERNAME"] == "guestuser"

    def test_web_super_admin_username_setter(self, monkeypatch):
        config = Config()
        config.WEB_SUPER_ADMIN_USERNAME = "adminuser"
        assert os.environ["ZRB_WEB_SUPER_ADMIN_USERNAME"] == "adminuser"

    def test_web_super_admin_password_setter(self, monkeypatch):
        config = Config()
        config.WEB_SUPER_ADMIN_PASSWORD = "adminpass"
        assert os.environ["ZRB_WEB_SUPER_ADMIN_PASSWORD"] == "adminpass"

    def test_web_access_token_cookie_name_setter(self, monkeypatch):
        config = Config()
        config.WEB_ACCESS_TOKEN_COOKIE_NAME = "at"
        assert os.environ["ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME"] == "at"

    def test_web_refresh_token_cookie_name_setter(self, monkeypatch):
        config = Config()
        config.WEB_REFRESH_TOKEN_COOKIE_NAME = "rt"
        assert os.environ["ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME"] == "rt"

    def test_web_secret_key_setter(self, monkeypatch):
        config = Config()
        config.WEB_SECRET_KEY = "secret"
        assert os.environ["ZRB_WEB_SECRET_KEY"] == "secret"

    def test_web_auth_enabled_setter(self, monkeypatch):
        config = Config()
        config.WEB_AUTH_ENABLED = True
        assert os.environ["ZRB_WEB_AUTH_ENABLED"] == "on"

    def test_web_auth_access_token_expire_setter(self, monkeypatch):
        config = Config()
        config.WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES = 10
        assert os.environ["ZRB_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES"] == "10"

    def test_web_auth_refresh_token_expire_setter(self, monkeypatch):
        config = Config()
        config.WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES = 20
        assert os.environ["ZRB_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES"] == "20"

    def test_web_title_setter(self, monkeypatch):
        config = Config()
        config.WEB_TITLE = "title"
        assert os.environ["ZRB_WEB_TITLE"] == "title"

    def test_web_jargon_setter(self, monkeypatch):
        config = Config()
        config.WEB_JARGON = "jargon"
        assert os.environ["ZRB_WEB_JARGON"] == "jargon"

    def test_web_homepage_intro_setter(self, monkeypatch):
        config = Config()
        config.WEB_HOMEPAGE_INTRO = "intro"
        assert os.environ["ZRB_WEB_HOMEPAGE_INTRO"] == "intro"
