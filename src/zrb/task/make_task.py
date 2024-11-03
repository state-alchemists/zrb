from collections.abc import Callable
from typing import Any
from .any_task import AnyTask
from .base_task import BaseTask
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..context.any_shared_context import AnySharedContext
from ..context.any_context import AnyContext


def make_task(
    name: str,
    color: int | None = None,
    icon: str | None = None,
    description: str | None = None,
    cli_only: bool = False,
    input: list[AnyInput] | AnyInput | None = None,
    env: list[AnyEnv] | AnyEnv | None = None,
    execute_condition: bool | str | Callable[[AnySharedContext], bool] = True,
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
) -> Callable[[Callable[[AnyContext], Any]], AnyTask]:

    def _make_task(fn: Callable[[AnyContext], Any]) -> BaseTask:
        return BaseTask(
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
        )

    return _make_task
