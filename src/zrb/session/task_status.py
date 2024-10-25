import datetime


class TaskStatus():
    def __init__(self):
        self._started_at: datetime.datetime | None = None
        self._ready_at: datetime.datetime | None = None
        self._completed_at: datetime.datetime | None = None
        self._skipped_at: datetime.datetime | None = None
        self._permanently_failed_at: datetime.datetime | None = None

    def __repr__(self):
        return f"<TaskStatus {self.__get_status()}>"

    def __get_status(self) -> str:
        if self.is_permanently_failed():
            return "Permanently failed"
        if self.is_completed():
            return "Completed"
        if self.is_ready():
            return "Ready"
        if self.is_skipped():
            return "Skipped"
        if self.is_started():
            return "Started"

    def mark_as_started(self):
        self._started_at = datetime.datetime.now()

    def mark_as_ready(self):
        self._ready_at = datetime.datetime.now()

    def mark_as_completed(self):
        self._completed_at = datetime.datetime.now()

    def mark_as_skipped(self):
        self._skipped_at = datetime.datetime.now()

    def mark_as_permanently_failed(self):
        self._permanently_failed_at = datetime.datetime.now()

    def is_started(self):
        return self._started_at is not None

    def is_ready(self):
        return self._ready_at is not None

    def is_completed(self):
        return self._completed_at is not None

    def is_skipped(self):
        return self._skipped_at is not None

    def is_permanently_failed(self):
        return self._permanently_failed_at is not None

    def allow_run_downstream(self):
        return self.is_skipped() or self.is_started() or self.is_ready()
