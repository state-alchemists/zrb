import os

from zrb.action.runner import Runner
from zrb.helper.task import show_lines
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Callable, Iterable, List, Mapping, Optional, Union
from zrb.helper.util import to_human_readable
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


@typechecked
def create_wiki_tasks(
    directory: str,
    group: Optional[Group] = None,
    inputs: Iterable[AnyInput] = [],
    envs: Iterable[Env] = [],
    env_files: Iterable[EnvFile] = [],
    icon: Optional[str] = None,
    color: Optional[str] = None,
    upstreams: Iterable[AnyTask] = [],
    fallbacks: Iterable[AnyTask] = [],
    on_triggered: Optional[OnTriggered] = None,
    on_waiting: Optional[OnWaiting] = None,
    on_skipped: Optional[OnSkipped] = None,
    on_started: Optional[OnStarted] = None,
    on_ready: Optional[OnReady] = None,
    on_retry: Optional[OnRetry] = None,
    on_failed: Optional[OnFailed] = None,
    should_execute: Union[bool, str, Callable[..., bool]] = True,
    runner: Optional[Runner] = None,
):
    abs_directory = os.path.abspath(directory)
    directory_structure = _get_directory_structure(abs_directory)
    tasks: List[AnyTask] = []
    for file_name in directory_structure["files"]:
        if not file_name.endswith(".md"):
            continue
        task_name = file_name[:-3]
        task_description = f"Article about {to_human_readable(task_name)}"
        task = Task(
            name=task_name,
            group=group,
            description=task_description,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            upstreams=upstreams,
            fallbacks=fallbacks,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            should_execute=should_execute,
            run=_create_function(directory=directory, file_name=file_name),
        )
        if runner is not None:
            runner.register(task)
        tasks.append(task)
    for dir_name in directory_structure["dirs"]:
        sub_group_description = f"Articles related to {to_human_readable(dir_name)}"
        sub_group = Group(
            name=dir_name,
            parent=group,
            description=sub_group_description,
        )
        sub_tasks = create_wiki_tasks(
            directory=os.path.join(abs_directory, dir_name),
            group=sub_group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            upstreams=upstreams,
            fallbacks=fallbacks,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            should_execute=should_execute,
            runner=runner,
        )
        tasks = tasks + sub_tasks
    return tasks


def _create_function(directory: str, file_name: str) -> Callable[..., Any]:
    def fn(*args: Any, **kwargs: Any):
        with open(os.path.join(directory, file_name)) as f:
            content = f.read()
            lines = content.split("\n")
            show_lines(kwargs["_task"], *lines)

    return fn


def _get_directory_structure(path) -> Mapping[str, List[str]]:
    contents = {"files": [], "dirs": []}
    for item in os.listdir(path):
        full_path = os.path.join(path, item)
        if os.path.isdir(full_path):
            contents["dirs"].append(item)
        elif os.path.isfile(full_path):
            contents["files"].append(item)
    return contents
