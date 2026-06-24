"""Internet search provider config: SerpAPI, Brave, SearXNG, and which method to use."""

from __future__ import annotations

import os

from zrb.config.env_field import EnvField


class InternetSearchMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_SEARCH_INTERNET_METHOD: str = "google_rss"
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

    SEARCH_INTERNET_METHOD = EnvField(
        str, doc="One of: google_rss (default), serpapi, brave, searxng."
    )

    # BRAVE_API_KEY / SERPAPI_KEY use bare (un-prefixed) env vars by design, so
    # they stay hand-written rather than going through EnvField (which always
    # prefixes with ENV_PREFIX).
    @property
    def BRAVE_API_KEY(self) -> str:
        return os.getenv("BRAVE_API_KEY", self.DEFAULT_BRAVE_API_KEY)

    @BRAVE_API_KEY.setter
    def BRAVE_API_KEY(self, value: str):
        os.environ["BRAVE_API_KEY"] = value

    BRAVE_API_SAFE = EnvField(
        str, doc="Safe search filter for Brave API results (on/off)."
    )

    BRAVE_API_LANG = EnvField(
        str, doc="Language code for Brave search results (e.g. en)."
    )

    @property
    def SERPAPI_KEY(self) -> str:
        return os.getenv("SERPAPI_KEY", self.DEFAULT_SERPAPI_KEY)

    @SERPAPI_KEY.setter
    def SERPAPI_KEY(self, value: str):
        os.environ["SERPAPI_KEY"] = value

    SERPAPI_SAFE = EnvField(str, doc="Safe search filter for SerpAPI results (on/off).")

    SERPAPI_LANG = EnvField(
        str, doc="Language code for SerpAPI search results (e.g. en)."
    )

    SEARXNG_PORT = EnvField(int, doc="Port for the locally-running SearXNG instance.")

    SEARXNG_BASE_URL = EnvField(
        str,
        default_factory=lambda cfg: (
            cfg.DEFAULT_SEARXNG_BASE_URL or f"http://localhost:{cfg.SEARXNG_PORT}"
        ),
        doc="Base URL for the SearXNG instance. Defaults to http://localhost:<SEARXNG_PORT>.",
    )

    SEARXNG_SAFE = EnvField(
        int, doc="Safe search level for SearXNG (0=none, 1=moderate, 2=strict)."
    )

    SEARXNG_LANG = EnvField(
        str, doc="Language code for SearXNG search results (e.g. en-US)."
    )
