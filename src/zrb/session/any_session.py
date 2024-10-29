from __future__ import annotations  # Enables forward references
from typing import Coroutine, TYPE_CHECKING
from abc import ABC, abstractmethod
from ..context.any_context import AnyContext
from ..context.any_shared_context import AnySharedContext
from ..task_status.task_status import TaskStatus

if TYPE_CHECKING:
    from ..task import any_task


class AnySession(ABC):
    """Abstract base class for managing task execution and context in a session.

    This class handles task lifecycle management, context retrieval,
    deferred task execution, and data exchange between tasks using
    XCom-like functionality.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name this session"""
        pass

    @property
    @abstractmethod
    def status(self) -> dict[any_task.AnyTask, TaskStatus]:
        """Global task status of this session"""
        pass

    @property
    @abstractmethod
    def shared_ctx(self) -> AnySharedContext:
        """Shared context for this session"""
        pass

    @abstractmethod
    def terminate(self):
        """Terminating session"""
        pass

    @property
    @abstractmethod
    def is_terminated(self) -> bool:
        """Whether session is terminated or not"""
        pass

    @abstractmethod
    def get_ctx(self, task: any_task.AnyTask) -> AnyContext:
        """Retrieves the context for a specific task.

        Args:
            task (AnyTask): The task for which to retrieve the context.

        Returns:
            AnyContext: The context object specific to the provided task.
        """
        pass

    @abstractmethod
    def defer_monitoring(self, task: any_task.AnyTask, coro: Coroutine):
        """Defers the execution of a task's monitoring coroutine for later processing.

        Args:
            task (AnyTask): The task associated with the coroutine.
            coro (Coroutine): The monitoring coroutine to defer.
        """
        pass

    @abstractmethod
    async def wait_deferred_monitoring(self):
        """Asynchronously waits for all deferred monitoring coroutines to complete."""
        pass

    @abstractmethod
    def defer_action(self, task: any_task.AnyTask, coro: Coroutine):
        """Defers the execution of a task's coroutine for later processing.

        Args:
            task (AnyTask): The task associated with the coroutine.
            coro (Coroutine): The coroutine to defer.
        """
        pass

    @abstractmethod
    async def wait_deferred_action(self):
        """Asynchronously waits for all deferred task coroutines to complete."""
        pass

    @abstractmethod
    def register_task(self, task: any_task.AnyTask):
        """Registers a new task in the session.

        Args:
            task (AnyTask): The task to register in the session.
        """
        pass

    @abstractmethod
    def get_root_tasks(self, task: any_task.AnyTask) -> list[any_task.AnyTask]:
        """Retrieves the list of root tasks that should be executed first
        to run the given task.

        Args:
            task (AnyTask): The current task.

        Returns:
            list[AnyTask]: A list of root tasks.
        """
        pass

    @abstractmethod
    def get_next_tasks(self, task: any_task.AnyTask) -> list[any_task.AnyTask]:
        """Retrieves the list of tasks that should be executed after the given task.

        Args:
            task (AnyTask): The current task.

        Returns:
            list[AnyTask]: A list of tasks that should be executed next.
        """
        pass

    @abstractmethod
    def get_task_status(self, task: any_task.AnyTask) -> TaskStatus:
        """Get tasks' status.

        Args:
            task (AnyTask): The task to mark as started.

        Returns:
            TaskStatus: Task status object
        """
        pass

    @abstractmethod
    def is_allowed_to_run(self, task: any_task.AnyTask):
        """Determines if the specified task is allowed to run based on its current state.

        Args:
            task (AnyTask): The task to check.

        Returns:
            bool: True if the task is allowed to run, False otherwise.
        """
        pass
