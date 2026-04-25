"""Hook config: enable toggle, hook dirs, timeout, debug, log level."""

from __future__ import annotations

import os

from zrb.config.helper import get_env
from zrb.util.string.conversion import to_boolean


class HooksMixin:
    def __init__(self):
        self.DEFAULT_HOOKS_ENABLED: str = "on"
        self.DEFAULT_HOOKS_DIRS: str = ""
        self.DEFAULT_HOOKS_TIMEOUT: str = "30000"
        self.DEFAULT_HOOKS_DEBUG: str = "off"
        self.DEFAULT_HOOKS_LOG_LEVEL: str = "INFO"
        super().__init__()

    @property
    def HOOKS_ENABLED(self) -> bool:
        return to_boolean(
            get_env("HOOKS_ENABLED", self.DEFAULT_HOOKS_ENABLED, self.ENV_PREFIX)
        )

    @HOOKS_ENABLED.setter
    def HOOKS_ENABLED(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_HOOKS_ENABLED"] = "on" if value else "off"

    @property
    def HOOKS_DIRS(self) -> list[str]:
        dirs_str = get_env("HOOKS_DIRS", self.DEFAULT_HOOKS_DIRS, self.ENV_PREFIX)
        if dirs_str != "":
            return [path.strip() for path in dirs_str.split(":") if path.strip() != ""]
        return []

    @HOOKS_DIRS.setter
    def HOOKS_DIRS(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_HOOKS_DIRS"] = ":".join(value)

    @property
    def HOOKS_TIMEOUT(self) -> int:
        """Timeout in milliseconds for hook execution."""
        return int(
            get_env("HOOKS_TIMEOUT", self.DEFAULT_HOOKS_TIMEOUT, self.ENV_PREFIX)
        )

    @HOOKS_TIMEOUT.setter
    def HOOKS_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_HOOKS_TIMEOUT"] = str(value)

    @property
    def HOOKS_DEBUG(self) -> bool:
        return to_boolean(
            get_env("HOOKS_DEBUG", self.DEFAULT_HOOKS_DEBUG, self.ENV_PREFIX)
        )

    @HOOKS_DEBUG.setter
    def HOOKS_DEBUG(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_HOOKS_DEBUG"] = "on" if value else "off"

    @property
    def HOOKS_LOG_LEVEL(self) -> str:
        return get_env("HOOKS_LOG_LEVEL", self.DEFAULT_HOOKS_LOG_LEVEL, self.ENV_PREFIX)

    @HOOKS_LOG_LEVEL.setter
    def HOOKS_LOG_LEVEL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_HOOKS_LOG_LEVEL"] = value
