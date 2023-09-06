from zrb.helper.typecheck import typechecked
from zrb.helper.typing import List, Mapping
from zrb.task_group.group import Group
from zrb.task.any_task import AnyTask
from zrb.task_env.env import Env
from zrb.helper.string.jinja import is_probably_jinja


@typechecked
def fetch_env_map_from_group(
    env_map: Mapping[str, str], group: Group
) -> Mapping[str, str]:
    for task in group.get_tasks():
        env_map = fetch_env_map_from_task(env_map, task)
    for sub_group in group.get_children():
        sub_env_map: Mapping[str, str] = fetch_env_map_from_group(
            env_map, sub_group
        )
        env_map = cascade_env_map(env_map, sub_env_map)
    return env_map


@typechecked
def fetch_env_map_from_task(
    env_map: Mapping[str, str], task: AnyTask
):
    task_env_map: Mapping[str, str] = {}
    for env_file in task.get_env_files():
        envs = env_file.get_envs()
        task_env_map = add_envs_to_env_map(task_env_map, envs)
    task_env_map = add_envs_to_env_map(task_env_map, task._envs)
    env_map = cascade_env_map(env_map, task_env_map)
    for upstream in task.get_upstreams():
        task_env_map = fetch_env_map_from_task(env_map, upstream)
    for checker in task.get_checkers():
        task_env_map = fetch_env_map_from_task(env_map, checker)
    return env_map


@typechecked
def add_envs_to_env_map(
    env_map: Mapping[str, str], envs: List[Env]
) -> Mapping[str, str]:
    for env in envs:
        if env.os_name == '':
            continue
        env_name = get_env_name(env)
        env_default = get_env_default(env)
        env_map[env_name] = env_default
    return env_map


@typechecked
def cascade_env_map(
    env_map: Mapping[str, str],
    other_env_map: Mapping[str, str]
) -> Mapping[str, str]:
    for key, value in other_env_map.items():
        if key in env_map:
            continue
        env_map[key] = value
    return env_map


@typechecked
def get_env_name(env: Env) -> str:
    if env.os_name is None:
        return env.name
    return env.os_name


@typechecked
def get_env_default(env: Env) -> str:
    if is_probably_jinja(env.default):
        return ''
    return env.default
