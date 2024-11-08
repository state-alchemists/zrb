from typing import Any, TypedDict


class TaskStatusHistoryStateLog(TypedDict):
    status: str
    time: str


class TaskStatusStateLog(TypedDict):
    history: list[TaskStatusHistoryStateLog]
    is_started: bool
    is_ready: bool
    is_completed: bool
    is_skipped: bool
    is_failed: bool
    is_permanently_failed: bool


class SessionStateLog(TypedDict):
    name: str
    start_time: str
    path: list[str]
    input: dict[str, Any]
    final_result: str
    finished: bool
    log: list[str]
    task_status: dict[str, TaskStatusStateLog]


class SessionStateLogs(TypedDict):
    total: int
    data: list[SessionStateLog]
