"""Internet search provider config: SerpAPI, Brave, SearXNG, and which method to use."""

from __future__ import annotations

import os

from zrb.config.helper import get_env


class InternetSearchMixin:
    def __init__(self):
        self.DEFAULT_SEARCH_INTERNET_METHOD: str = "serpapi"
        self.DEFAULT_BRAVE_API_KEY: str = ""
        self.DEFAULT_BRAVE_API_SAFE: str = "off"
        self.DEFAULT_BRAVE_API_LANG: str = "en"
        self.DEFAULT_SERPAPI_KEY: str = ""
        self.DEFAULT_SERPAPI_SAFE: str = "off"
        self.DEFAULT_SERPAPI_LANG: str = "en"
        self.DEFAULT_SEARXNG_PORT: str = "8080"
        self.DEFAULT_SEARXNG_BASE_URL: str = ""
        self.DEFAULT_SEARXNG_SAFE: str = "0"
        self.DEFAULT_SEARXNG_LANG: str = "en-US"
        super().__init__()

    @property
    def SEARCH_INTERNET_METHOD(self) -> str:
        """Either serpapi or searxng."""
        return get_env(
            "SEARCH_INTERNET_METHOD",
            self.DEFAULT_SEARCH_INTERNET_METHOD,
            self.ENV_PREFIX,
        )

    @SEARCH_INTERNET_METHOD.setter
    def SEARCH_INTERNET_METHOD(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SEARCH_INTERNET_METHOD"] = value

    @property
    def BRAVE_API_KEY(self) -> str:
        return os.getenv("BRAVE_API_KEY", self.DEFAULT_BRAVE_API_KEY)

    @BRAVE_API_KEY.setter
    def BRAVE_API_KEY(self, value: str):
        os.environ["BRAVE_API_KEY"] = value

    @property
    def BRAVE_API_SAFE(self) -> str:
        return get_env("BRAVE_API_SAFE", self.DEFAULT_BRAVE_API_SAFE, self.ENV_PREFIX)

    @BRAVE_API_SAFE.setter
    def BRAVE_API_SAFE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_BRAVE_API_SAFE"] = value

    @property
    def BRAVE_API_LANG(self) -> str:
        return get_env("BRAVE_API_LANG", self.DEFAULT_BRAVE_API_LANG, self.ENV_PREFIX)

    @BRAVE_API_LANG.setter
    def BRAVE_API_LANG(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_BRAVE_API_LANG"] = value

    @property
    def SERPAPI_KEY(self) -> str:
        return os.getenv("SERPAPI_KEY", self.DEFAULT_SERPAPI_KEY)

    @SERPAPI_KEY.setter
    def SERPAPI_KEY(self, value: str):
        os.environ["SERPAPI_KEY"] = value

    @property
    def SERPAPI_SAFE(self) -> str:
        return get_env("SERPAPI_SAFE", self.DEFAULT_SERPAPI_SAFE, self.ENV_PREFIX)

    @SERPAPI_SAFE.setter
    def SERPAPI_SAFE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SERPAPI_SAFE"] = value

    @property
    def SERPAPI_LANG(self) -> str:
        return get_env("SERPAPI_LANG", self.DEFAULT_SERPAPI_LANG, self.ENV_PREFIX)

    @SERPAPI_LANG.setter
    def SERPAPI_LANG(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SERPAPI_LANG"] = value

    @property
    def SEARXNG_PORT(self) -> int:
        return int(get_env("SEARXNG_PORT", self.DEFAULT_SEARXNG_PORT, self.ENV_PREFIX))

    @SEARXNG_PORT.setter
    def SEARXNG_PORT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_PORT"] = str(value)

    @property
    def SEARXNG_BASE_URL(self) -> str:
        default = self.DEFAULT_SEARXNG_BASE_URL
        if default == "":
            default = f"http://localhost:{self.SEARXNG_PORT}"
        return get_env("SEARXNG_BASE_URL", default, self.ENV_PREFIX)

    @SEARXNG_BASE_URL.setter
    def SEARXNG_BASE_URL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_BASE_URL"] = value

    @property
    def SEARXNG_SAFE(self) -> int:
        return int(get_env("SEARXNG_SAFE", self.DEFAULT_SEARXNG_SAFE, self.ENV_PREFIX))

    @SEARXNG_SAFE.setter
    def SEARXNG_SAFE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_SAFE"] = str(value)

    @property
    def SEARXNG_LANG(self) -> str:
        return get_env("SEARXNG_LANG", self.DEFAULT_SEARXNG_LANG, self.ENV_PREFIX)

    @SEARXNG_LANG.setter
    def SEARXNG_LANG(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_LANG"] = value
