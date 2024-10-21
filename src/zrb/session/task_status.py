class TaskStatus():
    def __init__(self):
        self._started: bool = False
        self._completed: bool = False

    def __repr__(self):
        return f"<TaskStatus started={self._started} completed={self._completed}>"

    def mark_as_started(self):
        self._started = True

    def mark_as_completed(self):
        self._completed = True

    def is_started(self):
        return self._started

    def is_completed(self):
        return self._completed
