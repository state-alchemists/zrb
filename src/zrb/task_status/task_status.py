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

    def reset(self):
        self._is_started = False
        self._is_ready = False
        self._is_completed = False
        self._is_skipped = False
        self._is_failed = False
        self._is_permanently_failed = False
        self._history.append((TASK_RESET, datetime.datetime.now()))

    def mark_as_started(self):
        self._is_failed = False
        self._is_started = True
        self._history.append((TASK_STARTED, datetime.datetime.now()))

    def mark_as_failed(self):
        self._is_failed = True
        self._history.append((TASK_FAILED, datetime.datetime.now()))

    def mark_as_ready(self):
        self._is_ready = True
        self._history.append((TASK_READY, datetime.datetime.now()))

    def mark_as_completed(self):
        self._is_completed = True
        self._history.append((TASK_COMPLETED, datetime.datetime.now()))

    def mark_as_skipped(self):
        self._is_skipped = True
        self._history.append((TASK_SKIPPED, datetime.datetime.now()))

    def mark_as_permanently_failed(self):
        self._is_permanently_failed = True
        self._history.append((TASK_PERMANENTLY_FAILED, datetime.datetime.now()))

    def mark_as_terminated(self):
        if not self._is_terminated:
            self._is_terminated = True
            if not (self.is_skipped or self.is_completed or self.is_permanently_failed):
                self._history.append((TASK_TERMINATED, datetime.datetime.now()))

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
        if self.is_failed or self.is_permanently_failed or self.is_terminated:
            return False
        return self.is_skipped or self.is_ready

    @property
    def history(self):
        return self._history
