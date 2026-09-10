import datetime

TASK_STARTED = "started"
TASK_READY = "ready"
TASK_COMPLETED = "completed"
TASK_SKIPPED = "skipped"
TASK_FAILED = "failed"
TASK_PERMANENTLY_FAILED = "permanently-failed"
TASK_TERMINATED = "terminated"
TASK_RESET = "reset"


class TaskStatus:
    def __init__(self):
        self._history: list[tuple[str, datetime.datetime]] = []
        self._is_started: bool = False
        self._is_ready: bool = False
        self._is_completed: bool = False
        self._is_skipped: bool = False
        self._is_failed: bool = False
        self._is_permanently_failed: bool = False
        self._is_terminated: bool = False

    def __repr__(self):
        return f"<TaskStatus {self._history}>"

    def reset_history(self):
        self._history = []

    def _record(self, status: str):
        self._history.append((status, datetime.datetime.now()))

    def reset(self):
        self._is_started = False
        self._is_ready = False
        self._is_completed = False
        self._is_skipped = False
        self._is_failed = False
        self._is_permanently_failed = False
        self._record(TASK_RESET)

    def mark_as_started(self):
        self._is_failed = False
        self._is_started = True
        self._record(TASK_STARTED)

    def mark_as_failed(self):
        self._is_failed = True
        self._record(TASK_FAILED)

    def mark_as_ready(self):
        self._is_ready = True
        self._record(TASK_READY)

    def mark_as_completed(self):
        self._is_completed = True
        self._record(TASK_COMPLETED)

    def mark_as_skipped(self):
        self._is_skipped = True
        self._record(TASK_SKIPPED)

    def mark_as_permanently_failed(self):
        self._is_permanently_failed = True
        self._record(TASK_PERMANENTLY_FAILED)

    def mark_as_terminated(self):
        if not self._is_terminated:
            self._is_terminated = True
            if not (self.is_skipped or self.is_completed or self.is_permanently_failed):
                self._record(TASK_TERMINATED)

    @property
    def is_started(self) -> bool:
        return self._is_started

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def is_completed(self) -> bool:
        return self._is_completed

    @property
    def is_skipped(self) -> bool:
        return self._is_skipped

    @property
    def is_failed(self) -> bool:
        return self._is_failed

    @property
    def is_permanently_failed(self) -> bool:
        return self._is_permanently_failed

    @property
    def is_terminated(self) -> bool:
        return self._is_terminated

    @property
    def allow_run_downstream(self):
        # Permanent failure only: `is_failed` is per-attempt and cleared on the
        # next retry's mark_as_started, so gating on it races with the retry
        # loop of a readiness-checked task and silently drops downstream tasks.
        if self.is_permanently_failed or self.is_terminated:
            return False
        return self.is_skipped or self.is_ready

    @property
    def history(self):
        return self._history
