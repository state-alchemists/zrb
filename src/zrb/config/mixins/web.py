"""Web-UI config: HTTP server, auth, branding, pagination, shutdown timeout."""

from __future__ import annotations

import os

from zrb.config.helper import get_env
from zrb.util.string.conversion import to_boolean


class WebMixin:
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

    @property
    def WEB_CSS_PATH(self) -> list[str]:
        web_css_path_str = get_env(
            "WEB_CSS_PATH", self.DEFAULT_WEB_CSS_PATH, self.ENV_PREFIX
        )
        if web_css_path_str != "":
            return [
                path.strip()
                for path in web_css_path_str.split(":")
                if path.strip() != ""
            ]
        return []

    @WEB_CSS_PATH.setter
    def WEB_CSS_PATH(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_WEB_CSS_PATH"] = ":".join(value)

    @property
    def WEB_JS_PATH(self) -> list[str]:
        web_js_path_str = get_env(
            "WEB_JS_PATH", self.DEFAULT_WEB_JS_PATH, self.ENV_PREFIX
        )
        if web_js_path_str != "":
            return [
                path.strip()
                for path in web_js_path_str.split(":")
                if path.strip() != ""
            ]
        return []

    @WEB_JS_PATH.setter
    def WEB_JS_PATH(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_WEB_JS_PATH"] = ":".join(value)

    @property
    def WEB_FAVICON_PATH(self) -> str:
        return get_env(
            "WEB_FAVICON_PATH", self.DEFAULT_WEB_FAVICON_PATH, self.ENV_PREFIX
        )

    @WEB_FAVICON_PATH.setter
    def WEB_FAVICON_PATH(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_FAVICON_PATH"] = value

    @property
    def WEB_COLOR(self) -> str:
        return get_env("WEB_COLOR", self.DEFAULT_WEB_COLOR, self.ENV_PREFIX)

    @WEB_COLOR.setter
    def WEB_COLOR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_COLOR"] = value

    @property
    def WEB_HTTP_PORT(self) -> int:
        return int(
            get_env("WEB_HTTP_PORT", self.DEFAULT_WEB_HTTP_PORT, self.ENV_PREFIX)
        )

    @WEB_HTTP_PORT.setter
    def WEB_HTTP_PORT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_HTTP_PORT"] = str(value)

    @property
    def WEB_GUEST_USERNAME(self) -> str:
        return get_env(
            "WEB_GUEST_USERNAME", self.DEFAULT_WEB_GUEST_USERNAME, self.ENV_PREFIX
        )

    @WEB_GUEST_USERNAME.setter
    def WEB_GUEST_USERNAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_GUEST_USERNAME"] = value

    @property
    def WEB_SUPER_ADMIN_USERNAME(self) -> str:
        return get_env(
            "WEB_SUPER_ADMIN_USERNAME",
            self.DEFAULT_WEB_SUPER_ADMIN_USERNAME,
            self.ENV_PREFIX,
        )

    @WEB_SUPER_ADMIN_USERNAME.setter
    def WEB_SUPER_ADMIN_USERNAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_SUPER_ADMIN_USERNAME"] = value

    @property
    def WEB_SUPER_ADMIN_PASSWORD(self) -> str:
        return get_env(
            "WEB_SUPER_ADMIN_PASSWORD",
            self.DEFAULT_WEB_SUPER_ADMIN_PASSWORD,
            self.ENV_PREFIX,
        )

    @WEB_SUPER_ADMIN_PASSWORD.setter
    def WEB_SUPER_ADMIN_PASSWORD(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_SUPER_ADMIN_PASSWORD"] = value

    @property
    def WEB_ACCESS_TOKEN_COOKIE_NAME(self) -> str:
        return get_env(
            "WEB_ACCESS_TOKEN_COOKIE_NAME",
            self.DEFAULT_WEB_ACCESS_TOKEN_COOKIE_NAME,
            self.ENV_PREFIX,
        )

    @WEB_ACCESS_TOKEN_COOKIE_NAME.setter
    def WEB_ACCESS_TOKEN_COOKIE_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_ACCESS_TOKEN_COOKIE_NAME"] = value

    @property
    def WEB_REFRESH_TOKEN_COOKIE_NAME(self) -> str:
        return get_env(
            "WEB_REFRESH_TOKEN_COOKIE_NAME",
            self.DEFAULT_WEB_REFRESH_TOKEN_COOKIE_NAME,
            self.ENV_PREFIX,
        )

    @WEB_REFRESH_TOKEN_COOKIE_NAME.setter
    def WEB_REFRESH_TOKEN_COOKIE_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_REFRESH_TOKEN_COOKIE_NAME"] = value

    @property
    def WEB_SECRET_KEY(self) -> str:
        return get_env("WEB_SECRET_KEY", self.DEFAULT_WEB_SECRET_KEY, self.ENV_PREFIX)

    @WEB_SECRET_KEY.setter
    def WEB_SECRET_KEY(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_SECRET_KEY"] = value

    @property
    def WEB_ENABLE_AUTH(self) -> bool:
        return to_boolean(
            get_env("WEB_ENABLE_AUTH", self.DEFAULT_WEB_ENABLE_AUTH, self.ENV_PREFIX)
        )

    @WEB_ENABLE_AUTH.setter
    def WEB_ENABLE_AUTH(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_WEB_ENABLE_AUTH"] = "on" if value else "off"

    @property
    def WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(
            get_env(
                "WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES",
                self.DEFAULT_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
                self.ENV_PREFIX,
            )
        )

    @WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES.setter
    def WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES"] = str(
            value
        )

    @property
    def WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(
            get_env(
                "WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES",
                self.DEFAULT_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
                self.ENV_PREFIX,
            )
        )

    @WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES.setter
    def WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES"] = str(
            value
        )

    @property
    def WEB_TITLE(self) -> str:
        return get_env("WEB_TITLE", self.DEFAULT_WEB_TITLE, self.ENV_PREFIX)

    @WEB_TITLE.setter
    def WEB_TITLE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_TITLE"] = value

    @property
    def WEB_JARGON(self) -> str:
        return get_env("WEB_JARGON", self.DEFAULT_WEB_JARGON, self.ENV_PREFIX)

    @WEB_JARGON.setter
    def WEB_JARGON(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_JARGON"] = value

    @property
    def WEB_HOMEPAGE_INTRO(self) -> str:
        return get_env(
            "WEB_HOMEPAGE_INTRO", self.DEFAULT_WEB_HOMEPAGE_INTRO, self.ENV_PREFIX
        )

    @WEB_HOMEPAGE_INTRO.setter
    def WEB_HOMEPAGE_INTRO(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_HOMEPAGE_INTRO"] = value

    @property
    def WEB_SHUTDOWN_TIMEOUT(self) -> int:
        """Graceful shutdown timeout in milliseconds for web server."""
        return int(
            get_env(
                "WEB_SHUTDOWN_TIMEOUT",
                self.DEFAULT_WEB_SHUTDOWN_TIMEOUT,
                self.ENV_PREFIX,
            )
        )

    @WEB_SHUTDOWN_TIMEOUT.setter
    def WEB_SHUTDOWN_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_SHUTDOWN_TIMEOUT"] = str(value)

    @property
    def WEB_SESSION_PAGE_SIZE(self) -> int:
        """Default page size for session listings."""
        return int(
            get_env(
                "WEB_SESSION_PAGE_SIZE",
                self.DEFAULT_WEB_SESSION_PAGE_SIZE,
                self.ENV_PREFIX,
            )
        )

    @WEB_SESSION_PAGE_SIZE.setter
    def WEB_SESSION_PAGE_SIZE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_SESSION_PAGE_SIZE"] = str(value)

    @property
    def WEB_API_PAGE_SIZE(self) -> int:
        """Default page size for API listings."""
        return int(
            get_env(
                "WEB_API_PAGE_SIZE",
                self.DEFAULT_WEB_API_PAGE_SIZE,
                self.ENV_PREFIX,
            )
        )

    @WEB_API_PAGE_SIZE.setter
    def WEB_API_PAGE_SIZE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_API_PAGE_SIZE"] = str(value)

    @property
    def WEB_TASK_SESSION_PAGE_SIZE(self) -> int:
        """Default page size for task session listings."""
        return int(
            get_env(
                "WEB_TASK_SESSION_PAGE_SIZE",
                self.DEFAULT_WEB_TASK_SESSION_PAGE_SIZE,
                self.ENV_PREFIX,
            )
        )

    @WEB_TASK_SESSION_PAGE_SIZE.setter
    def WEB_TASK_SESSION_PAGE_SIZE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_TASK_SESSION_PAGE_SIZE"] = str(value)
