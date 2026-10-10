from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, overload

from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.session.any_session import AnySession


class AnyTask(ABC):
    """The contract every task type implements: identity, DAG edges,
    input/env aggregation, and the run/exec entry points."""

    @overload
    def __rshift__(self, other: "AnyTask") -> "AnyTask": ...

    @overload
    def __rshift__(self, other: "Sequence[AnyTask]") -> "Sequence[AnyTask]": ...

    @abstractmethod
    def __rshift__(
        self, other: "AnyTask | Sequence[AnyTask]"
    ) -> "AnyTask | Sequence[AnyTask]":
        pass

    @abstractmethod
    def __lshift__(self, other: "AnyTask | Sequence[AnyTask]") -> "AnyTask":
        pass

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
    def is_cli_only(self) -> bool:
        """Whether the task is CLI only or not"""
        pass

    @property
    @abstractmethod
    def own_inputs(self) -> list[AnyInput]:
        """Inputs this task declares itself, without its upstreams'."""
        pass

    @property
    @abstractmethod
    def own_envs(self) -> list[AnyEnv]:
        """Envs this task declares itself, without its upstreams'."""
        pass

    @property
    @abstractmethod
    def inputs(self) -> list[AnyInput]:
        """Task inputs, merged with those of every transitive upstream."""
        pass

    @property
    @abstractmethod
    def envs(self) -> list[AnyEnv]:
        """Task envs, merged with those of every transitive upstream."""
        pass

    @property
    @abstractmethod
    def upstreams(self) -> list["AnyTask"]:
        """Tasks that must complete before this one starts."""
        pass

    @property
    @abstractmethod
    def fallbacks(self) -> list["AnyTask"]:
        """Tasks to run if this task ultimately fails."""
        pass

    @property
    @abstractmethod
    def successors(self) -> list["AnyTask"]:
        """Tasks to run after this task succeeds."""
        pass

    @property
    @abstractmethod
    def readiness_checks(self) -> list["AnyTask"]:
        """Tasks that must succeed before this task is considered ready."""
        pass

    @abstractmethod
    def append_fallback(self, fallbacks: "AnyTask | Sequence[AnyTask]"):
        """Add one or more fallback tasks."""
        pass

    @abstractmethod
    def append_successor(self, successors: "AnyTask | Sequence[AnyTask]"):
        """Add one or more successor tasks."""
        pass

    @abstractmethod
    def append_readiness_check(self, readiness_checks: "AnyTask | Sequence[AnyTask]"):
        """Add one or more readiness-check tasks."""
        pass

    @abstractmethod
    def append_upstream(self, upstreams: "AnyTask | Sequence[AnyTask]"):
        """Add one or more upstream tasks that this task depends on."""
        pass

    @abstractmethod
    def get_ctx(self, session: "AnySession") -> "AnyContext":
        """Build this task's execution context within `session`."""

    @abstractmethod
    def run(
        self,
        session: "AnySession | None" = None,
        str_kwargs: dict[str, str] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """Run the task synchronously within *session*, returning its result.

        `str_kwargs`/`kwargs` seed input values as strings or already-typed
        values, respectively.
        """
        pass

    @abstractmethod
    async def async_run(
        self,
        session: "AnySession | None" = None,
        str_kwargs: dict[str, str] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """`run`'s async counterpart, for callers already inside an event loop."""
        pass

    @abstractmethod
    async def exec_root_tasks(self, session: "AnySession"):
        """Run this task's root upstreams and everything downstream of them,
        until this task itself is ready."""
        pass

    @abstractmethod
    async def exec_chain(self, session: "AnySession"):
        """Run this task and everything downstream of it."""
        pass

    @abstractmethod
    async def exec(self, session: "AnySession"):
        """Run this task alone, without its upstreams or downstreams."""
        pass

    @abstractmethod
    def to_function(self) -> Callable[..., Any]:
        """Turn a task into a function"""
        pass
