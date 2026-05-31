"""LLM UI runtime knobs: status / refresh / flush intervals and buffer size."""

from __future__ import annotations

from zrb.config.env_field import EnvField


class LLMUIRuntimeMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_UI_STATUS_INTERVAL: str = "1000"
        self.DEFAULT_LLM_UI_LONG_STATUS_INTERVAL: str = "60000"
        self.DEFAULT_LLM_UI_REFRESH_INTERVAL: str = "500"
        self.DEFAULT_LLM_UI_FLUSH_INTERVAL: str = "500"
        self.DEFAULT_LLM_UI_MAX_BUFFER_SIZE: str = "2000"
        super().__init__()

    LLM_UI_STATUS_INTERVAL = EnvField(
        int, doc="Interval in milliseconds for UI status checks."
    )

    LLM_UI_LONG_STATUS_INTERVAL = EnvField(
        int, doc="Interval in milliseconds for long-running UI status checks."
    )

    LLM_UI_REFRESH_INTERVAL = EnvField(
        int, doc="Interval in milliseconds for UI refresh."
    )

    LLM_UI_FLUSH_INTERVAL = EnvField(
        int, doc="Interval in milliseconds for UI buffer flush."
    )

    LLM_UI_MAX_BUFFER_SIZE = EnvField(int, doc="Maximum buffer size for UI output.")
