from collections.abc import Callable
from typing import Any
from .any_task import AnyTask
from .base_task import BaseTask
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..session.context import Context


def make_task(
    name: str,
    color: int | None = None,
    icon: str | None = None,
    description: str | None = None,
    inputs: list[AnyInput] | AnyInput | None = None,
    envs: list[AnyEnv] | AnyEnv | None = None,
    retries: int = 2,
    retry_period: float = 0,
    readiness_checks: list[AnyTask] | None = None,
    readiness_check_delay: float = 0,
    readiness_check_period: float = 0,
    upstreams: list[AnyTask] | AnyTask | None = None,
    fallbacks: list[AnyTask] | AnyTask | None = None,
) -> Callable[[Callable[[Context], Any]], AnyTask]:

    def _make_task(fn: Callable[[Context], Any]) -> BaseTask:
        return BaseTask(
            name=name,
            color=color,
            icon=icon,
            description=description,
            inputs=inputs,
            envs=envs,
            action=fn,
            retries=retries,
            retry_period=retry_period,
            readiness_checks=readiness_checks,
            readiness_check_delay=readiness_check_delay,
            readiness_check_period=readiness_check_period,
            upstreams=upstreams,
            fallbacks=fallbacks,
        )

    return _make_task
