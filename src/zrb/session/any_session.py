from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Coroutine

from zrb.context.any_context import AnyContext
from zrb.group.any_group import AnyGroup
from zrb.session_state_logger.any_session_state_logger import AnySessionStateLogger
from zrb.task_status.task_status import TaskStatus
from zrb.util.pydantic_schema import PydanticInstanceSchemaMixin

if TYPE_CHECKING:
    from zrb.context.any_shared_context import AnySharedContext
    from zrb.session_state_log.session_state_log import SessionStateLog
    from zrb.task.any_task import AnyTask


class AnySession(PydanticInstanceSchemaMixin, ABC):
    """One execution run's task graph state: each task's `Context`, status,
    and deferred coroutines, plus the shared context tasks read/write
    through."""

    @property
    @abstractmethod
    def name(self) -> str:
        """This session's name."""
        pass

    @property
    @abstractmethod
    def root_group(self) -> AnyGroup | None:
        """The group the main task was resolved from, if any."""
        pass

    @property
    @abstractmethod
    def task_names(self) -> list[str]:
        """Names of every task registered in this session so far."""
        pass

    @property
    @abstractmethod
    def shared_ctx(self) -> "AnySharedContext":
        """The context every task in this session reads inputs/envs/xcom from."""
        pass

    @abstractmethod
    def terminate(self):
        """Mark this session terminated, cancelling its deferred coroutines."""
        pass

    @property
    @abstractmethod
    def is_terminated(self) -> bool:
        """Whether `terminate` has been called on this session."""
        pass

    @property
    @abstractmethod
    def parent(self) -> "AnySession | None":
        """The session that spawned this one, for a callback or sub-task."""
        pass

    @property
    @abstractmethod
    def task_path(self) -> list[str]:
        """The main task's group path, as CLI words."""
        pass

    @property
    @abstractmethod
    def final_result(self) -> Any:
        """The main task's result, once it has finished."""
        pass

    @property
    @abstractmethod
    def state_logger(self) -> AnySessionStateLogger:
        """The sink this session's state is persisted through."""
        pass

    @abstractmethod
    def set_main_task(self, main_task: "AnyTask"):
        """Set the task this session was started to run."""
        pass

    @abstractmethod
    def as_state_log(self) -> "SessionStateLog":
        pass

    @abstractmethod
    def get_ctx(self, task: "AnyTask") -> AnyContext:
        """This session's `Context` for *task*, registering it first if new."""
        pass

    @abstractmethod
    def defer_monitoring(
        self, task: "AnyTask", coro: Coroutine[Any, Any, Any] | asyncio.Task[Any]
    ):
        """Track *task*'s readiness-monitoring coroutine, so `wait_deferred`
        and `terminate` can reach it."""
        pass

    @abstractmethod
    def defer_action(
        self, task: "AnyTask", coro: Coroutine[Any, Any, Any] | asyncio.Task[Any]
    ):
        """Track *task*'s action coroutine; cancelled immediately if the
        session is already terminated."""
        pass

    @abstractmethod
    def defer_coro(self, coro: Coroutine[Any, Any, Any] | asyncio.Task[Any]):
        """Track a coroutine not tied to any one task; cancelled immediately
        if the session is already terminated."""
        pass

    @abstractmethod
    async def wait_deferred(self):
        """Await every deferred coroutine tracked so far."""
        pass

    @abstractmethod
    def register_task(self, task: "AnyTask"):
        """Give *task* a `Context` and an xcom queue in this session, if it
        does not have one yet."""
        pass

    @abstractmethod
    def get_root_tasks(self, task: "AnyTask") -> list["AnyTask"]:
        """*task*'s transitive upstreams that have no upstream of their own —
        where execution of its chain starts."""
        pass

    @abstractmethod
    def get_next_tasks(self, task: "AnyTask") -> list["AnyTask"]:
        """Tasks registered as running directly after *task*."""
        pass

    @abstractmethod
    def get_task_status(self, task: "AnyTask") -> TaskStatus:
        """*task*'s status in this session, registering it first if new."""
        pass

    @abstractmethod
    def is_allowed_to_run(self, task: "AnyTask") -> bool:
        """Whether *task* can start now: the session isn't terminated, *task*
        hasn't already started or completed, and every upstream is done."""
        pass
