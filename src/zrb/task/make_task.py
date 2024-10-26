from collections.abc import Callable
from typing import Any
from .any_task import AnyTask
from .base_task import BaseTask
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..context.context import Context


def make_task(
    name: str,
    color: int | None = None,
    icon: str | None = None,
    description: str | None = None,
    input: list[AnyInput] | AnyInput | None = None,
    env: list[AnyEnv] | AnyEnv | None = None,
    execute_condition: bool | str | Callable[[Context], bool] = True,
    retries: int = 2,
    retry_period: float = 0,
    readiness_check: list[AnyTask] | AnyTask | None = None,
    readiness_check_delay: float = 0,
    readiness_check_period: float = 0,
    upstream: list[AnyTask] | AnyTask | None = None,
    fallback: list[AnyTask] | AnyTask | None = None,
) -> Callable[[Callable[[Context], Any]], AnyTask]:

    def _make_task(fn: Callable[[Context], Any]) -> BaseTask:
        return BaseTask(
            name=name,
            color=color,
            icon=icon,
            description=description,
            input=input,
            env=env,
            action=fn,
            execute_condition=execute_condition,
            retries=retries,
            retry_period=retry_period,
            readiness_check=readiness_check,
            readiness_check_delay=readiness_check_delay,
            readiness_check_period=readiness_check_period,
            upstream=upstream,
            fallback=fallback,
        )

    return _make_task
