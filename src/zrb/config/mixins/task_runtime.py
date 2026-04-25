"""Task runtime config: scheduler tick, HTTP/TCP check intervals, cmd buffer & cleanup."""

from __future__ import annotations

import os

from zrb.config.helper import get_env


class TaskRuntimeMixin:
    def __init__(self):
        self.DEFAULT_SCHEDULER_TICK_INTERVAL: str = "60000"
        self.DEFAULT_HTTP_CHECK_INTERVAL: str = "5000"
        self.DEFAULT_TCP_CHECK_INTERVAL: str = "5000"
        self.DEFAULT_TASK_READINESS_DELAY: str = "500"
        self.DEFAULT_CMD_CLEANUP_TIMEOUT: str = "2000"
        self.DEFAULT_CMD_BUFFER_LIMIT: str = "102400"
        super().__init__()

    @property
    def SCHEDULER_TICK_INTERVAL(self) -> int:
        """Interval in milliseconds for scheduler tick."""
        return int(
            get_env(
                "SCHEDULER_TICK_INTERVAL",
                self.DEFAULT_SCHEDULER_TICK_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @SCHEDULER_TICK_INTERVAL.setter
    def SCHEDULER_TICK_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_SCHEDULER_TICK_INTERVAL"] = str(value)

    @property
    def HTTP_CHECK_INTERVAL(self) -> int:
        """Interval in milliseconds for HTTP health checks."""
        return int(
            get_env(
                "HTTP_CHECK_INTERVAL",
                self.DEFAULT_HTTP_CHECK_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @HTTP_CHECK_INTERVAL.setter
    def HTTP_CHECK_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_HTTP_CHECK_INTERVAL"] = str(value)

    @property
    def TCP_CHECK_INTERVAL(self) -> int:
        """Interval in milliseconds for TCP health checks."""
        return int(
            get_env(
                "TCP_CHECK_INTERVAL",
                self.DEFAULT_TCP_CHECK_INTERVAL,
                self.ENV_PREFIX,
            )
        )

    @TCP_CHECK_INTERVAL.setter
    def TCP_CHECK_INTERVAL(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_TCP_CHECK_INTERVAL"] = str(value)

    @property
    def TASK_READINESS_DELAY(self) -> int:
        """Delay in milliseconds for task readiness checks."""
        return int(
            get_env(
                "TASK_READINESS_DELAY",
                self.DEFAULT_TASK_READINESS_DELAY,
                self.ENV_PREFIX,
            )
        )

    @TASK_READINESS_DELAY.setter
    def TASK_READINESS_DELAY(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_TASK_READINESS_DELAY"] = str(value)

    @property
    def CMD_CLEANUP_TIMEOUT(self) -> int:
        """Timeout in milliseconds for command process cleanup."""
        return int(
            get_env(
                "CMD_CLEANUP_TIMEOUT",
                self.DEFAULT_CMD_CLEANUP_TIMEOUT,
                self.ENV_PREFIX,
            )
        )

    @CMD_CLEANUP_TIMEOUT.setter
    def CMD_CLEANUP_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_CMD_CLEANUP_TIMEOUT"] = str(value)

    @property
    def CMD_BUFFER_LIMIT(self) -> int:
        """Buffer memory limit for command execution."""
        return int(
            get_env(
                "CMD_BUFFER_LIMIT",
                self.DEFAULT_CMD_BUFFER_LIMIT,
                self.ENV_PREFIX,
            )
        )

    @CMD_BUFFER_LIMIT.setter
    def CMD_BUFFER_LIMIT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_CMD_BUFFER_LIMIT"] = str(value)
