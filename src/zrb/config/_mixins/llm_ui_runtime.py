"""LLM UI runtime knobs: status / refresh / flush intervals and buffer size."""

from __future__ import annotations

import os

from zrb.config.helper import get_env


class LLMUIRuntimeMixin:
    def __init__(self):
        self.DEFAULT_LLM_UI_STATUS_INTERVAL: str = "1000"
        self.DEFAULT_LLM_UI_LONG_STATUS_INTERVAL: str = "60000"
        self.DEFAULT_LLM_UI_REFRESH_INTERVAL: str = "500"
        self.DEFAULT_LLM_UI_FLUSH_INTERVAL: str = "500"
        self.DEFAULT_LLM_UI_MAX_BUFFER_SIZE: str = "2000"
        super().__init__()

    @property
    def LLM_UI_STATUS_INTERVAL(self) -> int:
        """Interval in milliseconds for UI status checks."""
        return int(
            get_env(
                "LLM_UI_STATUS_INTERVAL",
                self.DEFAULT_LLM_UI_STATUS_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_STATUS_INTERVAL.setter
    def LLM_UI_STATUS_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STATUS_INTERVAL"] = str(value)

    @property
    def LLM_UI_LONG_STATUS_INTERVAL(self) -> int:
        """Interval in milliseconds for long-running UI status checks."""
        return int(
            get_env(
                "LLM_UI_LONG_STATUS_INTERVAL",
                self.DEFAULT_LLM_UI_LONG_STATUS_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_LONG_STATUS_INTERVAL.setter
    def LLM_UI_LONG_STATUS_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_LONG_STATUS_INTERVAL"] = str(value)

    @property
    def LLM_UI_REFRESH_INTERVAL(self) -> int:
        """Interval in milliseconds for UI refresh."""
        return int(
            get_env(
                "LLM_UI_REFRESH_INTERVAL",
                self.DEFAULT_LLM_UI_REFRESH_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_REFRESH_INTERVAL.setter
    def LLM_UI_REFRESH_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_REFRESH_INTERVAL"] = str(value)

    @property
    def LLM_UI_FLUSH_INTERVAL(self) -> int:
        """Interval in milliseconds for UI buffer flush."""
        return int(
            get_env(
                "LLM_UI_FLUSH_INTERVAL",
                self.DEFAULT_LLM_UI_FLUSH_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_FLUSH_INTERVAL.setter
    def LLM_UI_FLUSH_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_FLUSH_INTERVAL"] = str(value)

    @property
    def LLM_UI_MAX_BUFFER_SIZE(self) -> int:
        """Maximum buffer size for UI output."""
        return int(
            get_env(
                "LLM_UI_MAX_BUFFER_SIZE",
                self.DEFAULT_LLM_UI_MAX_BUFFER_SIZE,
                self.ENV_PREFIX,
            )
        )

    @LLM_UI_MAX_BUFFER_SIZE.setter
    def LLM_UI_MAX_BUFFER_SIZE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_MAX_BUFFER_SIZE"] = str(value)
