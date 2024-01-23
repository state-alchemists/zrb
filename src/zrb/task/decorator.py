from zrb.action.runner import Runner
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Callable, Iterable, Optional, Union
from zrb.task.any_task import AnyTask
from zrb.task.any_task_event_handler import (
    OnFailed,
    OnReady,
    OnRetry,
    OnSkipped,
    OnStarted,
    OnTriggered,
    OnWaiting,
)
from zrb.task.task import Task
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

# flake8: noqa E501


@typechecked
def python_task(
    name: str,
    group: Optional[Group] = None,
    inputs: Iterable[AnyInput] = [],
    envs: Iterable[Env] = [],
    env_files: Iterable[EnvFile] = [],
    icon: Optional[str] = None,
    color: Optional[str] = None,
    description: str = "",
    upstreams: Iterable[AnyTask] = [],
    on_triggered: Optional[OnTriggered] = None,
    on_waiting: Optional[OnWaiting] = None,
    on_skipped: Optional[OnSkipped] = None,
    on_started: Optional[OnStarted] = None,
    on_ready: Optional[OnReady] = None,
    on_retry: Optional[OnRetry] = None,
    on_failed: Optional[OnFailed] = None,
    checkers: Iterable[AnyTask] = [],
    checking_interval: float = 0.1,
    retry: int = 2,
    retry_interval: float = 1,
    should_execute: Union[bool, str, Callable[..., bool]] = True,
    return_upstream_result: bool = False,
    runner: Optional[Runner] = None,
) -> Callable[[Callable[..., Any]], Task]:
    """
    python_task decorator helps you turn any Python function into a task

    Returns:
        Callable[[Callable[..., Any]], Task]: A callable turning function into task.

    Examples:
        >>> from zrb import python_task
        >>> @python_task(
        >>>    name='my-task'
        >>> )
        >>> def my_task(*args, **kwargs):
        >>>    return 'hello world'
        >>> print(my_task)
        <Task name=my-task>
    """

    def _create_task(fn: Callable[..., Any]) -> Task:
        task = Task(
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            upstreams=upstreams,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            run=fn,
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
        )
        if runner is not None:
            runner.register(task)
        return task

    return _create_task
