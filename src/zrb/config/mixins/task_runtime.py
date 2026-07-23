"""Task runtime config: scheduler tick, HTTP/TCP check intervals, cmd buffer & cleanup."""

from __future__ import annotations

from zrb.config.env_field import EnvField


class TaskRuntimeMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_SCHEDULER_TICK_INTERVAL: str = "60000"
        self.DEFAULT_HTTP_CHECK_INTERVAL: str = "5000"
        self.DEFAULT_TCP_CHECK_INTERVAL: str = "5000"
        self.DEFAULT_TASK_READINESS_DELAY: str = "500"
        self.DEFAULT_TASK_READINESS_TIMEOUT: str = "0"
        self.DEFAULT_CMD_CLEANUP_TIMEOUT: str = "2000"
        self.DEFAULT_CMD_BUFFER_LIMIT: str = "102400"
        super().__init__()

    SCHEDULER_TICK_INTERVAL = EnvField(
        int, doc="Interval in milliseconds for scheduler tick."
    )

    HTTP_CHECK_INTERVAL = EnvField(
        int, doc="Interval in milliseconds for HTTP health checks."
    )

    TCP_CHECK_INTERVAL = EnvField(
        int, doc="Interval in milliseconds for TCP health checks."
    )

    TASK_READINESS_DELAY = EnvField(
        int, doc="Delay in milliseconds for task readiness checks."
    )

    TASK_READINESS_TIMEOUT = EnvField(
        int,
        doc=(
            "Aggregate timeout in milliseconds for the initial readiness wait. "
            "0 (default) disables the cap; a readiness check that never returns "
            "hangs the run. Set a positive value to fail fast instead."
        ),
    )

    CMD_CLEANUP_TIMEOUT = EnvField(
        int, doc="Timeout in milliseconds for command process cleanup."
    )

    CMD_BUFFER_LIMIT = EnvField(int, doc="Buffer memory limit for command execution.")
