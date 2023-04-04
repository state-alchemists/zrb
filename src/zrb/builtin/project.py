from typing import Any, List, Mapping
from ._group import project_group
from ..task.decorator import python_task
from ..task.base_task import Group, BaseTask
from ..task_env.env import Env
from ..task_input.bool_input import BoolInput
from ..runner import runner
from ..helper.string.jinja import is_probably_jinja


@python_task(
    name='get-default-env',
    description='Get default values for project environments',
    inputs=[
        BoolInput(
            name='export',
            shortcut='e',
            description='Whether add export statement or not',
            default=True
        )
    ],
    group=project_group,
    runner=runner
)
async def get_default_env(*args: Any, **kwargs: Any) -> str:
    env_map: Mapping[str, str] = {}
    env_map = fetch_env_map_from_group(env_map, project_group)
    env_keys = list(env_map.keys())
    env_keys.sort()
    should_export = kwargs.get('export', True)
    export_prefix = 'export ' if should_export else ''
    return '\n'.join([
        f'{export_prefix}{key}={env_map[key]}' for key in env_keys
    ])


def fetch_env_map_from_group(
    env_map: Mapping[str, str], group: Group
) -> Mapping[str, str]:
    for task in group.tasks:
        env_map = fetch_env_map_from_task(env_map, task)
    for sub_group in group.children:
        sub_env_map: Mapping[str, str] = fetch_env_map_from_group(
            env_map, sub_group
        )
        env_map = cascade_env_map(env_map, sub_env_map)
    return env_map


def fetch_env_map_from_task(
    env_map: Mapping[str, str], task: BaseTask
):
    task_env_map: Mapping[str, str] = {}
    for env_file in task.env_files:
        envs = env_file.get_envs()
        task_env_map = add_envs_to_env_map(task_env_map, envs)
    task_env_map = add_envs_to_env_map(task_env_map, task.envs)
    env_map = cascade_env_map(env_map, task_env_map)
    for upstream in task.upstreams:
        task_env_map = fetch_env_map_from_task(env_map, upstream)
    for checker in task.checkers:
        task_env_map = fetch_env_map_from_task(env_map, checker)
    return env_map


def add_envs_to_env_map(
    env_map: Mapping[str, str], envs: List[Env]
) -> Mapping[str, str]:
    for env in envs:
        if (
            env.os_name == '' or
            env.default == '' or
            is_probably_jinja(env.default)
        ):
            if env.name.startswith('FASTAPP'):
                print(env)
            continue
        env_map[env.os_name] = env.default
    return env_map


def cascade_env_map(
    env_map: Mapping[str, str],
    other_env_map: Mapping[str, str]
) -> Mapping[str, str]:
    for key, value in other_env_map.items():
        if key in env_map:
            continue
        env_map[key] = value
    return env_map
