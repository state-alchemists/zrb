from typing import (
    Any, Callable, Iterable, Optional
)
from typeguard import typechecked
from ..task_input.base_input import BaseInput
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_group.group import Group
from .base_task import BaseTask
from .task import Task


@typechecked
def python_task(
    name: str,
    group: Optional[Group] = None,
    inputs: Iterable[BaseInput] = [],
    envs: Iterable[Env] = [],
    env_files: Iterable[EnvFile] = [],
    icon: Optional[str] = None,
    color: Optional[str] = None,
    description: str = '',
    upstreams: Iterable[BaseTask] = [],
    checkers: Iterable[BaseTask] = [],
    checking_interval: float = 0.1,
    retry: int = 2,
    retry_interval: float = 1,
) -> Callable[[Callable[..., Any]], Task]:
    def _create_task(fn: Callable[..., Any]) -> Task:
        return Task(
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            upstreams=upstreams,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            run=fn
        )
    return _create_task
