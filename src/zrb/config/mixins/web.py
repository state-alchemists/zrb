"""Web-UI config: HTTP server, auth, branding, pagination, shutdown timeout."""

from __future__ import annotations

from zrb.config.env_field import EnvField, colon_join, colon_list, on_off, read_bool


class WebMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_WEB_CSS_PATH: str = ""
        self.DEFAULT_WEB_JS_PATH: str = ""
        self.DEFAULT_WEB_FAVICON_PATH: str = "/static/favicon-32x32.png"
        self.DEFAULT_WEB_COLOR: str = ""
        self.DEFAULT_WEB_HTTP_PORT: str = "21213"
        self.DEFAULT_WEB_GUEST_USERNAME: str = "user"
        self.DEFAULT_WEB_SUPER_ADMIN_USERNAME: str = "admin"
        self.DEFAULT_WEB_SUPER_ADMIN_PASSWORD: str = "admin"
        self.DEFAULT_WEB_ACCESS_TOKEN_COOKIE_NAME: str = "access_token"
        self.DEFAULT_WEB_REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
        self.DEFAULT_WEB_SECRET_KEY: str = "zrb"
        self.DEFAULT_WEB_ENABLE_AUTH: str = "off"
        self.DEFAULT_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: str = "30"
        self.DEFAULT_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES: str = "60"
        self.DEFAULT_WEB_TITLE: str = "Zrb"
        self.DEFAULT_WEB_JARGON: str = "Your Automation PowerHouse"
        self.DEFAULT_WEB_HOMEPAGE_INTRO: str = "Welcome to Zrb Web Interface"
        self.DEFAULT_WEB_SHUTDOWN_TIMEOUT: str = "10000"
        self.DEFAULT_WEB_SESSION_PAGE_SIZE: str = "20"
        self.DEFAULT_WEB_API_PAGE_SIZE: str = "20"
        self.DEFAULT_WEB_TASK_SESSION_PAGE_SIZE: str = "10"
        super().__init__()

    WEB_CSS_PATH = EnvField(colon_list, serialize=colon_join)

    WEB_JS_PATH = EnvField(colon_list, serialize=colon_join)

    WEB_FAVICON_PATH = EnvField(str)

    WEB_COLOR = EnvField(str)

    WEB_HTTP_PORT = EnvField(int)

    WEB_GUEST_USERNAME = EnvField(str)

    WEB_SUPER_ADMIN_USERNAME = EnvField(str)

    WEB_SUPER_ADMIN_PASSWORD = EnvField(str)

    WEB_ACCESS_TOKEN_COOKIE_NAME = EnvField(str)

    WEB_REFRESH_TOKEN_COOKIE_NAME = EnvField(str)

    WEB_SECRET_KEY = EnvField(str)

    WEB_ENABLE_AUTH = EnvField(read_bool, serialize=on_off)

    WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES = EnvField(int)

    WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES = EnvField(int)

    WEB_TITLE = EnvField(str)

    WEB_JARGON = EnvField(str)

    WEB_HOMEPAGE_INTRO = EnvField(str)

    WEB_SHUTDOWN_TIMEOUT = EnvField(
        int, doc="Graceful shutdown timeout in milliseconds for web server."
    )

    WEB_SESSION_PAGE_SIZE = EnvField(int, doc="Default page size for session listings.")

    WEB_API_PAGE_SIZE = EnvField(int, doc="Default page size for API listings.")

    WEB_TASK_SESSION_PAGE_SIZE = EnvField(
        int, doc="Default page size for task session listings."
    )
