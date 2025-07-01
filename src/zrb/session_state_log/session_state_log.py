from typing import Any

from pydantic import BaseModel


class TaskStatusHistoryStateLog(BaseModel):
    status: str
    time: str


class TaskStatusStateLog(BaseModel):
    history: list[TaskStatusHistoryStateLog]
    is_started: bool
    is_ready: bool
    is_completed: bool
    is_skipped: bool
    is_failed: bool
    is_permanently_failed: bool
    is_terminated: bool


class SessionStateLog(BaseModel):
    name: str
    start_time: str
    main_task_name: str
    path: list[str]
    input: dict[str, Any]
    final_result: str
    finished: bool
    log: list[str]
    task_status: dict[str, TaskStatusStateLog]


class SessionStateLogList(BaseModel):
    total: int
    data: list[SessionStateLog]
