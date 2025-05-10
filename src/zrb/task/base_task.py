import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from zrb.attr.type import BoolAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask
from zrb.task.base.context import (
    build_task_context,
    get_combined_envs,
    get_combined_inputs,
)
from zrb.task.base.execution import (
    execute_task_action,
    execute_task_chain,
    run_default_action,
)
from zrb.task.base.lifecycle import execute_root_tasks, run_and_cleanup, run_task_async
from zrb.task.base.operators import handle_lshift, handle_rshift


class BaseTask(AnyTask):
    """
    Implements a concrete task class `BaseTask` derived from the abstract base class `AnyTask`.

    This class serves as a robust and flexible task implementation that can be tailored for
    various execution scenarios within the Zrb framework. It supports functionalities such as:

    - **Task Definition and Initialization:** Setting up task attributes like `name`, `color`,
    `icon`, `description`, `cli_only`, `inputs`, `envs`, `action`, among others.
    - **Dependency Management:** Managing task dependencies using properties and methods to
    append upstreams, fallbacks, readiness checks, and successors, ensuring tasks are executed
    in the correct order and conditions.
    - **Execution Control:** Contains methods for both synchronous (`run`) and asynchronous
    execution (`async_run`), alongside internal task lifecycle methods (`exec_root_tasks`,
    `exec_chain`, `exec`).
    - **Readiness and Monitoring:** Supports readiness checks, retry mechanisms, and monitoring
    before task execution to ensure the task is executed under proper conditions.
    - **Operator Overloading:** Implements operators to handle task chaining and dependencies
    conveniently.
    """

    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: list[AnyInput | None] | AnyInput | None = None,
        env: list[AnyEnv | None] | AnyEnv | None = None,
        action: fstring | Callable[[AnyContext], Any] | None = None,
        execute_condition: BoolAttr = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
        upstream: list[AnyTask] | AnyTask | None = None,
        fallback: list[AnyTask] | AnyTask | None = None,
        successor: list[AnyTask] | AnyTask | None = None,
    ):
        caller_frame = inspect.stack()[1]
        self.__decl_file = caller_frame.filename
        self.__decl_line = caller_frame.lineno
        self._name = name
        self._color = color
        self._icon = icon
        self._description = description
        self._cli_only = cli_only
        self._inputs = input
        self._envs = env
        self._retries = retries
        self._retry_period = retry_period
        self._upstreams = upstream
        self._fallbacks = fallback
        self._successors = successor
        self._readiness_checks = readiness_check
        self._readiness_check_delay = readiness_check_delay
        self._readiness_check_period = readiness_check_period
        self._readiness_failure_threshold = readiness_failure_threshold
        self._readiness_timeout = readiness_timeout
        self._monitor_readiness = monitor_readiness
        self._execute_condition = execute_condition
        self._action = action

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name}>"

    def __rshift__(self, other: AnyTask | list[AnyTask]) -> AnyTask | list[AnyTask]:
        return handle_rshift(self, other)

    def __lshift__(self, other: AnyTask | list[AnyTask]) -> AnyTask:
        return handle_lshift(self, other)

    @property
    def name(self) -> str:
        return self._name

    @property
    def color(self) -> int | None:
        return self._color

    @property
    def icon(self) -> str | None:
        return self._icon

    @property
    def description(self) -> str:
        return self._description if self._description is not None else self.name

    @property
    def cli_only(self) -> bool:
        return self._cli_only

    @property
    def envs(self) -> list[AnyEnv]:
        return get_combined_envs(self)

    @property
    def inputs(self) -> list[AnyInput]:
        return get_combined_inputs(self)

    @property
    def fallbacks(self) -> list[AnyTask]:
        """Returns the list of fallback tasks."""
        if self._fallbacks is None:
            return []
        elif isinstance(self._fallbacks, list):
            return self._fallbacks
        return [self._fallbacks]  # Assume single task

    def append_fallback(self, fallbacks: AnyTask | list[AnyTask]):
        """Appends fallback tasks, ensuring no duplicates."""
        if self._fallbacks is None:
            self._fallbacks = []
        elif not isinstance(self._fallbacks, list):
            self._fallbacks = [self._fallbacks]
        to_add = fallbacks if isinstance(fallbacks, list) else [fallbacks]
        for fb in to_add:
            if fb not in self._fallbacks:
                self._fallbacks.append(fb)

    @property
    def successors(self) -> list[AnyTask]:
        """Returns the list of successor tasks."""
        if self._successors is None:
            return []
        elif isinstance(self._successors, list):
            return self._successors
        return [self._successors]  # Assume single task

    def append_successor(self, successors: AnyTask | list[AnyTask]):
        """Appends successor tasks, ensuring no duplicates."""
        if self._successors is None:
            self._successors = []
        elif not isinstance(self._successors, list):
            self._successors = [self._successors]
        to_add = successors if isinstance(successors, list) else [successors]
        for succ in to_add:
            if succ not in self._successors:
                self._successors.append(succ)

    @property
    def readiness_checks(self) -> list[AnyTask]:
        """Returns the list of readiness check tasks."""
        if self._readiness_checks is None:
            return []
        elif isinstance(self._readiness_checks, list):
            return self._readiness_checks
        return [self._readiness_checks]  # Assume single task

    def append_readiness_check(self, readiness_checks: AnyTask | list[AnyTask]):
        """Appends readiness check tasks, ensuring no duplicates."""
        if self._readiness_checks is None:
            self._readiness_checks = []
        elif not isinstance(self._readiness_checks, list):
            self._readiness_checks = [self._readiness_checks]
        to_add = (
            readiness_checks
            if isinstance(readiness_checks, list)
            else [readiness_checks]
        )
        for rc in to_add:
            if rc not in self._readiness_checks:
                self._readiness_checks.append(rc)

    @property
    def upstreams(self) -> list[AnyTask]:
        """Returns the list of upstream tasks."""
        if self._upstreams is None:
            return []
        elif isinstance(self._upstreams, list):
            return self._upstreams
        return [self._upstreams]  # Assume single task

    def append_upstream(self, upstreams: AnyTask | list[AnyTask]):
        """Appends upstream tasks, ensuring no duplicates."""
        if self._upstreams is None:
            self._upstreams = []
        elif not isinstance(self._upstreams, list):
            self._upstreams = [self._upstreams]
        to_add = upstreams if isinstance(upstreams, list) else [upstreams]
        for up in to_add:
            if up not in self._upstreams:
                self._upstreams.append(up)

    def get_ctx(self, session: AnySession) -> AnyContext:
        return build_task_context(self, session)

    def run(
        self, session: AnySession | None = None, str_kwargs: dict[str, str] = {}
    ) -> Any:
        """
        Synchronously runs the task and its dependencies, handling async setup and cleanup.

        Uses `asyncio.run()` internally, which creates a new event loop.
        WARNING: Do not call this method from within an already running asyncio
        event loop, as it will raise a RuntimeError. Use `async_run` instead
        if you are in an async context.

        Args:
            session (AnySession | None): The session to use. If None, a new one
                might be created implicitly.
            str_kwargs (dict[str, str]): String-based key-value arguments for inputs.

        Returns:
            Any: The final result of the main task execution.
        """
        # Use asyncio.run() to execute the async cleanup wrapper
        return asyncio.run(run_and_cleanup(self, session, str_kwargs))

    async def async_run(
        self, session: AnySession | None = None, str_kwargs: dict[str, str] = {}
    ) -> Any:
        return await run_task_async(self, session, str_kwargs)

    async def exec_root_tasks(self, session: AnySession):
        return await execute_root_tasks(self, session)

    async def exec_chain(self, session: AnySession):
        return await execute_task_chain(self, session)

    async def exec(self, session: AnySession):
        return await execute_task_action(self, session)

    async def _exec_action(self, ctx: AnyContext) -> Any:
        """
        Execute the main action of the task.
        This is the primary method to override in subclasses for custom action logic.
        The default implementation handles the '_action' attribute (string or callable).

        Args:
            ctx (AnyContext): The execution context for this task.

        Returns:
            Any: The result of the action execution.
        """
        try:
            # Delegate to the helper function for the default behavior
            return await run_default_action(self, ctx)
        except BaseException as e:
            additional_error_note = (
                f"Task: {self.name} ({self.__decl_file}:{self.__decl_line})"
            )
            if not isinstance(e, KeyboardInterrupt):
                # if error is KeyboardInterrupt, don't print anything
                ctx.log_error(additional_error_note)
            # Add definition location to the error
            if hasattr(e, "add_note"):
                e.add_note(additional_error_note)
            else:
                # fallback: use the __notes__ attribute directly
                e.__notes__ = getattr(e, "__notes__", []) + [additional_error_note]
            raise e
