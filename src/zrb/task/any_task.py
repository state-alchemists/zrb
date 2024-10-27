from __future__ import annotations  # Enables forward references
from typing import Any, TypeVar, TYPE_CHECKING
from abc import ABC, abstractmethod
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

    @property
    @abstractmethod
    def name(self) -> str:
        """Task name"""
        pass

    @property
    @abstractmethod
    def color(self) -> int | None:
        """Task color, if any."""
        pass

    @property
    @abstractmethod
    def icon(self) -> str | None:
        """Task icon, if any."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Task description"""
        pass

    @property
    @abstractmethod
    def inputs(self) -> list[AnyInput]:
        """Task inputs"""
        pass

    @property
    @abstractmethod
    def envs(self) -> list[AnyEnv]:
        """Task envs"""
        pass

    @property
    @abstractmethod
    def upstreams(self) -> list[TAnyTask]:
        """Task upstreams"""
        pass

    @property
    @abstractmethod
    def fallbacks(self) -> list[TAnyTask]:
        """Task fallbacks"""
        pass

    @property
    @abstractmethod
    def readiness_checks(self) -> list[TAnyTask]:
        """Task readiness checks"""
        pass

    @abstractmethod
    def append_upstreams(self, upstreams: TAnyTask | list[TAnyTask]):
        """Sets the upstream tasks that this task depends on.

        Args:
            upstreams (TAnyTask | list[TAnyTask]): A single upstream task or
                a list of upstream tasks.
        """
        pass

    @abstractmethod
    def run(self, session: session.AnySession | None = None) -> Any:
        """Runs the task synchronously.

        Args:
            session (AnySession): The shared session.

        Returns:
            Any: The result of the task execution.
        """
        pass

    @abstractmethod
    async def async_run(self, session: session.AnySession | None = None) -> Any:
        """Runs the task asynchronously.

        Args:
            session (AnySession): The shared session.

        Returns:
            Any: The result of the task execution.
        """
        pass

    @abstractmethod
    async def exec_root_tasks(self, session: session.AnySession):
        """Execute the root tasks along with the downstreams until the current task
        is ready.

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

    @abstractmethod
    async def exec(self, session: session.AnySession):
        """Execute the task (without upstream or downstream).

        Args:
            session (AnySession): The shared session.
        """
        pass

