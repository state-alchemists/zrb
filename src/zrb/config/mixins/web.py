"""Web-UI config: HTTP server, auth, branding, pagination, shutdown timeout."""

from __future__ import annotations

from zrb.config.env_field import EnvField, colon_join, colon_list, on_off
from zrb.util.string.conversion import to_boolean


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
        self.DEFAULT_WEB_AUTH_ENABLED: str = "off"
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

    WEB_CSS_PATH = EnvField(
        colon_list,
        serialize=colon_join,
        doc="Colon-separated paths to additional CSS files injected into the web UI.",
    )

    WEB_JS_PATH = EnvField(
        colon_list,
        serialize=colon_join,
        doc="Colon-separated paths to additional JavaScript files injected into the web UI.",
    )

    WEB_FAVICON_PATH = EnvField(
        str, doc="URL path to the favicon served by the web UI."
    )

    WEB_COLOR = EnvField(
        str, doc="Primary brand color for the web UI (CSS color value, e.g. #3b82f6)."
    )

    WEB_HTTP_PORT = EnvField(int, doc="HTTP port the web server listens on.")

    WEB_GUEST_USERNAME = EnvField(
        str, doc="Username for unauthenticated guest access when auth is disabled."
    )

    WEB_SUPER_ADMIN_USERNAME = EnvField(
        str, doc="Username for the built-in super-admin account."
    )

    WEB_SUPER_ADMIN_PASSWORD = EnvField(
        str, secret=True, doc="Password for the built-in super-admin account."
    )

    WEB_ACCESS_TOKEN_COOKIE_NAME = EnvField(
        str, doc="Cookie name used to store the JWT access token."
    )

    WEB_REFRESH_TOKEN_COOKIE_NAME = EnvField(
        str, doc="Cookie name used to store the JWT refresh token."
    )

    WEB_SECRET_KEY = EnvField(
        str,
        secret=True,
        doc="Secret key used to sign JWT tokens. Change this in production.",
    )

    WEB_AUTH_ENABLED = EnvField(
        to_boolean, serialize=on_off, doc="Enable/disable web authentication."
    )

    WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES = EnvField(
        int, doc="Access token expiry duration in minutes."
    )

    WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES = EnvField(
        int, doc="Refresh token expiry duration in minutes."
    )

    WEB_TITLE = EnvField(
        str, doc="Title shown in the web UI browser tab and page header."
    )

    WEB_JARGON = EnvField(str, doc="Tagline displayed in the web UI.")

    WEB_HOMEPAGE_INTRO = EnvField(
        str, doc="Introductory text shown on the web UI homepage."
    )

    WEB_SHUTDOWN_TIMEOUT = EnvField(
        int, doc="Graceful shutdown timeout in milliseconds for web server."
    )

    WEB_SESSION_PAGE_SIZE = EnvField(int, doc="Default page size for session listings.")

    WEB_API_PAGE_SIZE = EnvField(int, doc="Default page size for API listings.")

    WEB_TASK_SESSION_PAGE_SIZE = EnvField(
        int, doc="Default page size for task session listings."
    )
