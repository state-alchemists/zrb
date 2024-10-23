from typing import Any, Coroutine
from abc import ABC, abstractmethod
from .any_shared_context import AnySharedContext
from .any_context import AnyContext
from ..task.any_base_task import AnyBaseTask


class AnySession(ABC):
    """Abstract base class for managing task execution and context in a session.

    This class handles task lifecycle management, context retrieval, 
    deferred task execution, and data exchange between tasks using 
    XCom-like functionality.
    """

    @abstractmethod
    def get_shared_context(self) -> AnySharedContext:
        """Retrieves the shared context that is common across tasks in the session.

        Returns:
            AnySharedContext: The shared context object used across all tasks.
        """
        pass

    @abstractmethod
    def get_context(self, task: AnyBaseTask) -> AnyContext:
        """Retrieves the context for a specific task.

        Args:
            task (AnyBaseTask): The task for which to retrieve the context.

        Returns:
            AnyContext: The context object specific to the provided task.
        """
        pass

    @abstractmethod
    def defer_task_coroutine(self, task: AnyBaseTask, coro: Coroutine):
        """Defers the execution of a task's coroutine for later processing.

        Args:
            task (AnyBaseTask): The task associated with the coroutine.
            coro (Coroutine): The coroutine to defer.
        """
        pass

    @abstractmethod
    async def wait_deffered_task_coroutines(self):
        """Asynchronously waits for all deferred task coroutines to complete."""
        pass

    @abstractmethod
    def register_task(self, task: AnyBaseTask):
        """Registers a new task in the session.

        Args:
            task (AnyBaseTask): The task to register in the session.
        """
        pass

    @abstractmethod
    def get_tasks(self) -> list[AnyBaseTask]:
        """Returns the list of all tasks in the session.

        Returns:
            list[AnyBaseTask]: A list of tasks registered in the session.
        """
        pass

    @abstractmethod
    def get_next_tasks(self, task: AnyBaseTask) -> list[AnyBaseTask]:
        """Retrieves the list of tasks that should be executed after the given task.

        Args:
            task (AnyBaseTask): The current task.

        Returns:
            list[AnyBaseTask]: A list of tasks that should be executed next.
        """
        pass

    @abstractmethod
    def mark_task_as_started(self, task: AnyBaseTask):
        """Marks the specified task as started.

        Args:
            task (AnyBaseTask): The task to mark as started.
        """
        pass

    @abstractmethod
    def mark_task_as_ready(self, task: AnyBaseTask):
        """Marks the specified task as ready to be executed.

        Args:
            task (AnyBaseTask): The task to mark as ready.
        """
        pass

    @abstractmethod
    def mark_task_as_completed(self, task: AnyBaseTask):
        """Marks the specified task as completed.

        Args:
            task (AnyBaseTask): The task to mark as completed.
        """
        pass

    @abstractmethod
    def mark_task_as_skipped(self, task: AnyBaseTask):
        """Marks the specified task as skipped.

        Args:
            task (AnyBaseTask): The task to mark as skipped.
        """
        pass

    @abstractmethod
    def mark_task_as_permanently_failed(self, task: AnyBaseTask):
        """Marks the specified task as permanently failed.

        Args:
            task (AnyBaseTask): The task to mark as permanently failed.
        """
        pass

    @abstractmethod
    def peek_task_xcom(self, task: AnyBaseTask) -> Any:
        """Retrieves the last value exchanged between tasks (XCom) for the given task.

        Args:
            task (AnyBaseTask): The task for which to peek the XCom.

        Returns:
            Any: The last XCom value associated with the task.
        """
        pass

    @abstractmethod
    def append_task_xcom(self, task: AnyBaseTask, value: Any):
        """Appends a value to the XCom for the given task.

        Args:
            task (AnyBaseTask): The task for which to append the XCom.
            value (Any): The value to append to the XCom.
        """
        pass

    @abstractmethod
    def is_allowed_to_run(self, task: AnyBaseTask):
        """Determines if the specified task is allowed to run based on its current state.

        Args:
            task (AnyBaseTask): The task to check.

        Returns:
            bool: True if the task is allowed to run, False otherwise.
        """
        pass
