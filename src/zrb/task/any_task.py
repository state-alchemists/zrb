from __future__ import annotations  # Enables forward references

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.session.any_session import AnySession


class AnyTask(ABC):
    """Abstract base class defining the interface for all executable tasks within Zrb.

    This interface specifies the essential properties and methods that any concrete
    task implementation must provide. It covers:

    - **Metadata:** Properties like `name`, `description`, `color`, and `icon` for
      identification and UI representation.
    - **Configuration:** Properties for defining `inputs` (user-provided parameters)
      and `envs` (environment variables).
    - **Execution Control:** Properties like `cli_only` to restrict execution context.
    - **Dependency Management:** Properties for `upstreams` (prerequisites),
      `fallbacks` (error handling), `successors` (post-completion tasks), and
      `readiness_checks` (for long-running tasks). Methods like `append_*` allow
      programmatic modification of these dependencies.
    - **Context Management:** `get_ctx` method to retrieve the task's specific
      execution context.
    - **Execution Methods:** `run` (synchronous) and `async_run` (asynchronous)
      entry points, along with internal execution helpers (`exec_root_tasks`,
      `exec_chain`, `exec`) defining the execution lifecycle.

    Concrete task classes (like `BaseTask`) inherit from `AnyTask` and provide
    the actual implementation for these abstract members.
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
    def cli_only(self) -> bool:
        """Whether the task is CLI only or not"""
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
    def upstreams(self) -> list["AnyTask"]:
        """Task upstreams"""
        pass

    @property
    @abstractmethod
    def fallbacks(self) -> list["AnyTask"]:
        """Task fallbacks"""
        pass

    @property
    @abstractmethod
    def successors(self) -> list["AnyTask"]:
        """Task successors"""
        pass

    @property
    @abstractmethod
    def readiness_checks(self) -> list["AnyTask"]:
        """Task readiness checks"""
        pass

    @abstractmethod
    def append_fallback(self, fallbacks: "AnyTask" | list["AnyTask"]):
        """Add the fallback tasks.

        Args:
            fallbacks (AnyTask | list[AnyTask]): A single fallback task or
                a list of fallback tasks.
        """
        pass

    @abstractmethod
    def append_successor(self, successors: "AnyTask" | list["AnyTask"]):
        """Add the successor tasks.

        Args:
            successors (AnyTask | list[AnyTask]): A single successor task or
                a list of successor tasks.
        """
        pass

    @abstractmethod
    def append_readiness_check(self, readiness_checks: "AnyTask" | list["AnyTask"]):
        """Add the readiness_check tasks.

        Args:
            readiness_checks (AnyTask | list[AnyTask]): A single readiness_check task or
                a list of readiness_check tasks.
        """
        pass

    @abstractmethod
    def append_upstream(self, upstreams: "AnyTask" | list["AnyTask"]):
        """Add the upstream tasks that this task depends on.

        Args:
            upstreams (AnyTask | list[AnyTask]): A single upstream task or
                a list of upstream tasks.
        """
        pass

    @abstractmethod
    def get_ctx(self, session: "AnySession") -> "AnyContext":
        pass

    @abstractmethod
    def run(
        self, session: "AnySession | None" = None, str_kwargs: dict[str, str] = {}
    ) -> Any:
        """Runs the task synchronously.

        Args:
            session (AnySession): The shared session.
            str_kwargs(dict[str, str]): The input string values.

        Returns:
            Any: The result of the task execution.
        """
        pass

    @abstractmethod
    async def async_run(
        self, session: "AnySession | None" = None, str_kwargs: dict[str, str] = {}
    ) -> Any:
        """Runs the task asynchronously.

        Args:
            session (AnySession): The shared session.
            str_kwargs(dict[str, str]): The input string values.

        Returns:
            Any: The result of the task execution.
        """
        pass

    @abstractmethod
    async def exec_root_tasks(self, session: "AnySession"):
        """Execute the root tasks along with the downstreams until the current task
        is ready.

        Args:
            session (AnySession): The shared session.
        """
        pass

    @abstractmethod
    async def exec_chain(self, session: "AnySession"):
        """Execute the task along with the downstreams.

        Args:
            session (AnySession): The shared session.
        """
        pass

    @abstractmethod
    async def exec(self, session: "AnySession"):
        """Execute the task (without upstream or downstream).

        Args:
            session (AnySession): The shared session.
        """
        pass
