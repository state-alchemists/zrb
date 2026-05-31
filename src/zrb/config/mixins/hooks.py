"""Hook config: enable toggle, hook dirs, timeout, debug, log level."""

from __future__ import annotations

from zrb.config.env_field import EnvField, colon_join, colon_list, on_off, read_bool


class HooksMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_HOOKS_ENABLED: str = "on"
        self.DEFAULT_HOOKS_DIRS: str = ""
        self.DEFAULT_HOOKS_TIMEOUT: str = "30000"
        self.DEFAULT_HOOKS_DEBUG: str = "off"
        self.DEFAULT_HOOKS_LOG_LEVEL: str = "INFO"
        super().__init__()

    HOOKS_ENABLED = EnvField(read_bool, serialize=on_off)

    HOOKS_DIRS = EnvField(colon_list, serialize=colon_join)

    HOOKS_TIMEOUT = EnvField(int, doc="Timeout in milliseconds for hook execution.")

    HOOKS_DEBUG = EnvField(read_bool, serialize=on_off)

    HOOKS_LOG_LEVEL = EnvField(str)
