import asyncio
import inspect
from collections.abc import Callable, Sequence
from typing import Any, overload

from zrb.attr.type import BoolAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.context.shared_context import SharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.task.base.context import BaseTaskContext
from zrb.task.base.execution import BaseTaskExecution
from zrb.task.base.lifecycle import BaseTaskLifecycle
from zrb.task.base.monitoring import BaseTaskMonitoring
from zrb.task.base.operators import BaseTaskOperators
from zrb.util.string.conversion import to_snake_case


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
        *,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: Sequence[AnyInput | None] | AnyInput | None = None,
        env: Sequence[AnyEnv | None] | AnyEnv | None = None,
        action: fstring | Callable[[AnyContext], Any] | None = None,
        execute_condition: BoolAttr = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: Sequence[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
        upstream: Sequence[AnyTask] | AnyTask | None = None,
        fallback: Sequence[AnyTask] | AnyTask | None = None,
        successor: Sequence[AnyTask] | AnyTask | None = None,
        print_fn: PrintFn | None = None,
    ):
        """Define a task.

        Only `name` is required; every other parameter has a working default,
        so `BaseTask(name="build")` is valid on its own.

        Args:
            name: Task name. Also the CLI sub-command name, so prefer
                kebab-case (`build-image`).
            color: 8-bit ANSI color code (0-255) for this task's log prefix.
                Defaults to one derived from the name.
            icon: Single-character emoji or glyph shown beside log lines.
            description: Help text shown by `zrb <group> <task> --help`.
                Defaults to `name`.
            cli_only: When True, hide this task from the web UI and expose it
                only on the CLI. Use for tasks that need a TTY.
            input: Input(s) prompted for before the task runs. Accepts a single
                `AnyInput` or a sequence. Inputs of upstream tasks are merged in
                automatically, so declare only what this task adds.
            env: Environment variable(s) visible to this task, as a single
                `AnyEnv` or a sequence.
            action: What the task does. Either a callable taking the task
                context, or an f-string template rendered against it. Subclasses
                (`CmdTask`, `LLMTask`) supply their own and ignore this.
            execute_condition: Whether the task should run at all. A bool, or a
                template/callable evaluated against the context at runtime; a
                falsy result marks the task skipped, not failed.
            retries: Number of *additional* attempts after a failure. The
                default of 2 means up to 3 total attempts.
            retry_period: Seconds to wait between retry attempts.
            readiness_check: Task(s) that must succeed before this task is
                considered ready. Presence of any check turns this into a
                long-running task: `run` returns once the checks pass, while
                the action keeps running in the background.
            readiness_check_delay: Seconds to wait after starting the action
                before the first readiness check.
            readiness_check_period: Seconds between readiness checks once
                monitoring, i.e. when `monitor_readiness` is True.
            readiness_failure_threshold: Consecutive readiness-check failures
                tolerated before the task is declared failed.
            readiness_timeout: Seconds a single readiness check may take before
                it counts as failed.
            monitor_readiness: When True, keep re-running readiness checks after
                the task is ready and restart the action if they start failing.
            upstream: Task(s) that must complete before this one starts.
                Equivalent to `other >> this`.
            fallback: Task(s) to run if this task ultimately fails.
            successor: Task(s) to run after this task succeeds.
            print_fn: Callable receiving this task's output lines. Defaults to
                printing to stdout.
        """
        # Optimized stack retrieval
        frame = inspect.currentframe()
        if frame is not None:
            caller_frame = frame.f_back
            self.__decl_file = (
                caller_frame.f_code.co_filename if caller_frame else "unknown"
            )
            self.__decl_line = caller_frame.f_lineno if caller_frame else 0
        else:
            self.__decl_file = "unknown"
            self.__decl_line = 0

        self._name = name
        self._color = color
        self._icon = icon
        self._description = description
        self._cli_only = cli_only
        self._inputs = input
        self._envs = env
        self._retries = retries
        self._retry_period = retry_period
        self._upstreams = self._ensure_task_list(upstream)
        self._fallbacks = self._ensure_task_list(fallback)
        self._successors = self._ensure_task_list(successor)
        self._readiness_checks = self._ensure_task_list(readiness_check)
        self._readiness_check_delay = readiness_check_delay
        self._readiness_check_period = readiness_check_period
        self._readiness_failure_threshold = readiness_failure_threshold
        self._readiness_timeout = readiness_timeout
        self._monitor_readiness = monitor_readiness
        self._execute_condition = execute_condition
        self._action = action
        self._print_fn = print_fn

        self._base_context = BaseTaskContext(self)
        self._base_execution = BaseTaskExecution(self)
        self._base_lifecycle = BaseTaskLifecycle(self)
        self._base_monitoring = BaseTaskMonitoring(self)
        self._base_operators = BaseTaskOperators(self)

    def _ensure_task_list(
        self, tasks: AnyTask | Sequence[AnyTask] | None
    ) -> list[AnyTask]:
        """Normalize a single task or a collection of them into a list.

        Tests sequence-ness rather than `isinstance(tasks, list)`, which is what
        these parameters' annotations have promised all along: a tuple used to
        take the single-task branch and be stored *as* a task, surfacing much
        later as `'tuple' object has no attribute 'name'`.

        The test is on the *collection* side, not `isinstance(tasks, AnyTask)`.
        Anything task-like that is not an `AnyTask` subclass — a stub, a
        `MagicMock`, a duck-typed adapter — must still land on the single-task
        branch, and testing the task side would send it to `list()` instead.

        `str`/`bytes` are rejected outright rather than falling through: both
        satisfy `Sequence`, so a bare string would otherwise spread into a list
        of its own characters and fail somewhere far away.
        """
        if tasks is None:
            return []
        if isinstance(tasks, (str, bytes)):
            raise TypeError(f"Expected a task or a sequence of tasks, got {tasks!r}")
        if isinstance(tasks, Sequence):
            return list(tasks)
        return [tasks]

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name}>"

    @overload
    def __rshift__(self, other: AnyTask) -> AnyTask: ...

    @overload
    def __rshift__(self, other: Sequence[AnyTask]) -> Sequence[AnyTask]: ...

    def __rshift__(
        self, other: AnyTask | Sequence[AnyTask]
    ) -> AnyTask | Sequence[AnyTask]:
        return self._base_operators.handle_rshift(other)

    def __lshift__(self, other: AnyTask | Sequence[AnyTask]) -> AnyTask:
        return self._base_operators.handle_lshift(other)

    @property
    def name(self) -> str:
        """The task's name, as used on the CLI."""
        return self._name

    @property
    def color(self) -> int | None:
        """8-bit ANSI color code for this task's log prefix, if one was set."""
        return self._color

    @property
    def icon(self) -> str | None:
        """Glyph shown beside this task's log lines, if one was set."""
        return self._icon

    @property
    def description(self) -> str:
        """Help text for this task, falling back to its name."""
        return self._description if self._description is not None else self.name

    @property
    def cli_only(self) -> bool:
        """Whether this task is hidden from the web UI."""
        return self._cli_only

    @property
    def execute_condition(self):
        """The raw condition deciding whether this task runs.

        Unevaluated: a bool, template string, or callable. Rendering it against
        a context is the execution layer's job.
        """
        return self._execute_condition

    @property
    def retries(self) -> int:
        """Additional attempts allowed after a failure (default 2)."""
        return self._retries if self._retries is not None else 2

    @property
    def retry_period(self) -> float:
        """Seconds to wait between retry attempts."""
        return self._retry_period if self._retry_period is not None else 0

    @property
    def readiness_check_delay(self) -> float:
        """Seconds to wait after the action starts before checking readiness."""
        return self._readiness_check_delay

    @property
    def readiness_check_period(self) -> float:
        """Seconds between readiness checks while monitoring (default 5)."""
        return self._readiness_check_period if self._readiness_check_period else 5.0

    @property
    def readiness_failure_threshold(self) -> int:
        """Consecutive readiness failures tolerated before failing (default 1)."""
        return (
            self._readiness_failure_threshold
            if self._readiness_failure_threshold
            else 1
        )

    @property
    def readiness_timeout(self) -> float:
        """Seconds a single readiness check may take before failing (default 60)."""
        return self._readiness_timeout if self._readiness_timeout else 60

    @property
    def monitor_readiness(self) -> bool:
        """Whether readiness keeps being re-checked after the task is ready."""
        return self._monitor_readiness if self._monitor_readiness is not None else False

    @property
    def action(self):
        """The raw action: a callable, an f-string template, or None."""
        return self._action

    @property
    def envs(self) -> list[AnyEnv]:
        """This task's environment variables, merged with those of its upstreams."""
        return self._base_context.get_combined_envs(task_envs=self._envs)

    @property
    def inputs(self) -> list[AnyInput]:
        """This task's inputs, merged with those of its upstreams."""
        return self._base_context.get_combined_inputs(task_inputs=self._inputs)

    def _append_unique_tasks(
        self, items: "AnyTask | Sequence[AnyTask]", target: "list[AnyTask]"
    ) -> None:
        """Appends tasks to target list, skipping duplicates."""
        to_add = self._ensure_task_list(items)
        for item in to_add:
            if item not in target:
                target.append(item)

    @property
    def fallbacks(self) -> list[AnyTask]:
        """Returns the list of fallback tasks."""
        return self._fallbacks

    def append_fallback(self, fallbacks: "AnyTask | Sequence[AnyTask]"):
        """Appends fallback tasks, ensuring no duplicates."""
        self._append_unique_tasks(fallbacks, self._fallbacks)

    @property
    def successors(self) -> list[AnyTask]:
        """Returns the list of successor tasks."""
        return self._successors

    def append_successor(self, successors: "AnyTask | Sequence[AnyTask]"):
        """Appends successor tasks, ensuring no duplicates."""
        self._append_unique_tasks(successors, self._successors)

    @property
    def readiness_checks(self) -> list[AnyTask]:
        """Returns the list of readiness check tasks."""
        return self._readiness_checks

    def append_readiness_check(self, readiness_checks: "AnyTask | Sequence[AnyTask]"):
        """Appends readiness check tasks, ensuring no duplicates."""
        self._append_unique_tasks(readiness_checks, self._readiness_checks)

    @property
    def upstreams(self) -> list[AnyTask]:
        """Returns the list of upstream tasks."""
        return self._upstreams

    def append_upstream(self, upstreams: "AnyTask | Sequence[AnyTask]"):
        """Appends upstream tasks, ensuring no duplicates."""
        self._append_unique_tasks(upstreams, self._upstreams)

    def get_ctx(self, session: AnySession) -> AnyContext:
        """Build this task's execution context within `session`.

        The context carries resolved inputs, envs, and the logging helpers the
        action uses. Call this when you need the same view of a session that
        the action receives.
        """
        return self._base_context.build_context(session)

    def run(
        self,
        session: AnySession | None = None,
        str_kwargs: dict[str, str] | None = None,
        kwargs: dict[str, Any] | None = None,
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
        try:
            return asyncio.run(
                self._base_lifecycle.run_and_cleanup(
                    session=session,
                    print_fn=self._print_fn,
                    str_kwargs=str_kwargs,
                    kwargs=kwargs,
                )
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            # Top-level interrupt (Ctrl+C / SIGINT), e.g. stopping
            # `zrb server start`. The async layers deliberately re-raise
            # cancellation so a cancelled session never looks successful to
            # programmatic callers; at this synchronous process-entry boundary
            # it just means the user asked to stop — exit quietly rather than
            # dumping a CancelledError traceback.
            return None

    async def async_run(
        self,
        session: AnySession | None = None,
        str_kwargs: dict[str, str] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """Run the task and its dependencies from inside an async context.

        The async counterpart of `run`, and the one to use when an event loop
        is already running.

        Args:
            session: Session to run in. A new one is created when omitted.
            str_kwargs: Input values as raw strings, parsed the way CLI
                arguments are.
            kwargs: Input values as already-typed Python objects.

        Returns:
            The result of the main task's action.
        """
        return await self._base_lifecycle.run_task_async(
            session=session,
            print_fn=self._print_fn,
            str_kwargs=str_kwargs,
            kwargs=kwargs,
        )

    async def exec_root_tasks(self, session: AnySession):
        """Run the dependency graph's roots, then cascade down to this task.

        Execution entry point used by the runners. Prefer `run`/`async_run`
        unless you are driving a session yourself.
        """
        return await self._base_lifecycle.execute_root_tasks(session)

    async def exec_chain(self, session: AnySession):
        """Run this task, then its successors, in order."""
        return await self._base_execution.execute_task_chain(session)

    async def exec(self, session: AnySession):
        """Run this task's own action, assuming upstreams already completed.

        Handles readiness checks, retries, and fallbacks. It does not run
        upstreams — `exec_root_tasks` does that.
        """
        return await self._base_execution.execute_task_action(session)

    async def exec_action(self, ctx: AnyContext) -> Any:
        """Public wrapper around _exec_action for cross-module callers.

        Also the single choke point for enriching a raised exception with this
        task's declaration site. Subclasses (`CmdTask`, `HttpCheck`,
        `TcpCheck`, `Scaffolder`, `Scheduler`, ...) override `_exec_action`
        wholesale rather than calling `super()`, so this enrichment lives here
        instead of inside `_exec_action` — every subclass gets it regardless
        of how it overrides the action itself.
        """
        try:
            return await self._exec_action(ctx)
        except (KeyboardInterrupt, GeneratorExit):
            raise
        except BaseException as e:
            additional_error_note = (
                f"Task: {self.name} ({self.__decl_file}:{self.__decl_line})"
            )
            if hasattr(e, "add_note"):
                e.add_note(additional_error_note)
            elif hasattr(e, "__notes__"):
                # fallback: use the __notes__ attribute directly
                e.__notes__ = getattr(e, "__notes__", []) + [additional_error_note]
            raise e

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
        return await self._base_execution.run_default_action(ctx)

    def to_function(self) -> Callable[..., Any]:
        """Wrap this task as a plain Python function.

        The returned function takes one keyword argument per task input, named
        in snake_case, and carries a generated `__name__`, `__doc__`, and
        `__signature__`. That makes it introspectable by anything expecting an
        ordinary callable — `help()`, IDEs, and LLM tool registration alike.

        Returns:
            A callable running this task in a fresh session and returning its
            result.
        """

        def task_runner_fn(**kwargs) -> Any:
            task_kwargs = self._get_func_kwargs(kwargs)
            shared_ctx = SharedContext(print_fn=self._print_fn)
            session = Session(shared_ctx=shared_ctx)
            return self.run(session=session, kwargs=task_kwargs)

        task_runner_fn.__doc__ = self._create_fn_docstring()
        setattr(task_runner_fn, "__signature__", self._create_fn_signature())
        task_runner_fn.__name__ = self.name
        return task_runner_fn

    def _get_func_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        fn_kwargs = {}
        for inp in self.inputs:
            snake_input_name = to_snake_case(inp.name)
            if snake_input_name in kwargs:
                fn_kwargs[inp.name] = kwargs[snake_input_name]
        return fn_kwargs

    def _create_fn_docstring(self) -> str:

        stub_shared_ctx = SharedContext(print_fn=self._print_fn)
        str_input_default_values = {}
        for inp in self.inputs:
            str_input_default_values[inp.name] = inp.get_default_str(stub_shared_ctx)
        doc = f"{self.description}\n\n"
        if len(self.inputs) > 0:
            doc += "Args:\n"
            for inp in self.inputs:
                str_input_default = str_input_default_values.get(inp.name, "")
                doc += (
                    f"    {inp.name}: {inp.description} (default: {str_input_default})"
                )
                doc += "\n"
        return doc

    def _create_fn_signature(self) -> inspect.Signature:
        params = []
        for inp in self.inputs:
            params.append(
                inspect.Parameter(
                    name=to_snake_case(inp.name),
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            )
        return inspect.Signature(params)
