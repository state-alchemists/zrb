from collections.abc import Callable, Sequence
from typing import Any

from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.group.any_group import AnyGroup
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask


def make_task(
    name: str,
    *,
    color: int | None = None,
    icon: str | None = None,
    description: str | None = None,
    cli_only: bool = False,
    input: Sequence[AnyInput | None] | AnyInput | None = None,
    env: Sequence[AnyEnv | None] | AnyEnv | None = None,
    execute_condition: bool | str | Callable[[AnyContext], bool] = True,
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
    group: AnyGroup | None = None,
    alias: str | None = None,
) -> Callable[[Callable[[AnyContext], Any]], AnyTask]:
    """Turn a function into a task, as a decorator.

    The decorated function becomes the task's `action`, so it takes the task
    context and returns whatever the task should produce. The name it was
    defined under is rebound to the resulting task, not to the function:

        from zrb import cli, make_task, StrInput

        @make_task(
            name="greet",
            input=StrInput("name", default="world"),
            group=cli,
        )
        def greet(ctx):
            return f"Hello, {ctx.input.name}"

        # `greet` is now an AnyTask; `zrb greet --name you` runs it.

    Passing `group=` registers the task in one step, which is the whole reason
    to prefer this over building a `Task` and registering it separately.

    Args:
        name: Task name, and the CLI sub-command name. Prefer kebab-case.
        group: Group to register the task under. When None the task is returned
            unregistered and is reachable only from Python.
        alias: CLI word addressing it inside *group*. Defaults to `name`.

    Every other parameter is `BaseTask`'s and behaves identically, except
    `action`, which is the decorated function.

    Returns:
        A decorator that replaces the function with the built task.
    """

    def _make_task(fn: Callable[[AnyContext], Any]) -> AnyTask:
        task = BaseTask(
            name=name,
            color=color,
            icon=icon,
            description=description,
            cli_only=cli_only,
            input=input,
            env=env,
            action=fn,
            execute_condition=execute_condition,
            retries=retries,
            retry_period=retry_period,
            readiness_check=readiness_check,
            readiness_check_delay=readiness_check_delay,
            readiness_check_period=readiness_check_period,
            readiness_failure_threshold=readiness_failure_threshold,
            readiness_timeout=readiness_timeout,
            monitor_readiness=monitor_readiness,
            upstream=upstream,
            fallback=fallback,
            successor=successor,
            print_fn=print_fn,
        )
        if group is not None:
            return group.add_task(task, alias=alias)
        return task

    return _make_task
