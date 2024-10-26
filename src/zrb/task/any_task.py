from __future__ import annotations  # Enables forward references
from typing import Any, TypeVar, TYPE_CHECKING
from abc import ABC, abstractmethod
from ..context.any_shared_context import AnySharedContext
from ..input.any_input import AnyInput
from ..env.any_env import AnyEnv

if TYPE_CHECKING:
    from ..session import session

TAnyTask = TypeVar("TAnyTask", bound="AnyTask")


class AnyTask(ABC):
    """Abstract base class representing a task in the system.

    This class defines the interface for tasks, including methods for retrieving
    task metadata (such as name, color, and description), handling inputs and
    environment variables, and managing task dependencies (upstreams and fallbacks).
    It also includes methods for running tasks synchronously or asynchronously.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Retrieves the name of the task.

        Returns:
            str: The name of the task.
        """
        pass

    @abstractmethod
    def get_color(self) -> int | None:
        """Retrieves the color associated with the task, if any.

        Returns:
            int | None: The color code representing the task, or None if no color is assigned.
        """
        pass

    @abstractmethod
    def get_icon(self) -> str | None:
        """Retrieves the icon associated with the task, if any.

        Returns:
            str | None: The icon code representing the task, or None if no icon is assigned.
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Retrieves the description of the task.

        Returns:
            str: A brief description of the task.
        """
        pass

    @abstractmethod
    def get_inputs(self) -> list[AnyInput]:
        """Retrieves the list of inputs required by the task.

        Returns:
            list[AnyInput]: A list of inputs necessary for the task execution.
        """
        pass

    @abstractmethod
    def get_envs(self) -> list[AnyEnv]:
        """Retrieves the list of environment variables required by the task.

        Returns:
            list[AnyEnv]: A list of environment variables used by the task.
        """
        pass

    @abstractmethod
    def get_upstreams(self) -> list[TAnyTask]:
        """Retrieves the list of upstream tasks that this task depends on.

        Returns:
            list[TAnyTask]: A list of tasks that must be completed before this task.
        """
        pass

    @abstractmethod
    def get_fallbacks(self) -> list[TAnyTask]:
        """Retrieves the list of fallback tasks in case this task fails.

        Returns:
            list[TAnyTask]: A list of fallback tasks to run if this task encounters an issue.
        """
        pass

    @abstractmethod
    def set_upstreams(self, upstreams: TAnyTask | list[TAnyTask]):
        """Sets the upstream tasks that this task depends on.

        Args:
            upstreams (TAnyTask | list[TAnyTask]): A single upstream task 
            or a list of upstream tasks.
        """
        pass

    @abstractmethod
    def get_readiness_checks(self) -> list[TAnyTask]:
        """Retrieves the readiness checks that must be satisfied before this task can run.

        Returns:
            list[TAnyTask]: A list of tasks that serve as readiness checks for this task.
        """
        pass

    @abstractmethod
    def run(self, shared_context: AnySharedContext | None = None) -> Any:
        """Runs the task synchronously.

        Args:
            shared_context (AnySharedContext, optional): The shared context for the task execution.

        Returns:
            Any: The result of the task execution.
        """
        pass

    @abstractmethod
    async def async_run(self, shared_context: AnySharedContext | None = None) -> Any:
        """Runs the task asynchronously.

        Args:
            shared_context (AnySharedContext, optional): The shared context for the task execution.

        Returns:
            Any: The result of the task execution.
        """
        pass

    @abstractmethod
    async def exec_root_tasks(self, session: session.AnySession):
        """Execute the root tasks along with the downstreams until the current task is ready.

        Args:
            session (AnySession): The shared session.
        """
        pass

    @abstractmethod
    async def exec_chain(self, session: session.AnySession):
        """Execute the task along with the downstreams.

        Args:
            session (AnySession): The shared session.
        """
        pass
