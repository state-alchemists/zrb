from zrb.helper.string.jinja import is_probably_jinja
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import List, Mapping
from zrb.task.any_task import AnyTask
from zrb.task_env.env import Env
from zrb.task_group.group import Group


@typechecked
def fetch_env_map_from_group(
    env_map: Mapping[str, str], group: Group
) -> Mapping[str, str]:
    for task in group.get_tasks():
        env_map = fetch_env_map_from_task(env_map, task)
    for sub_group in group.get_children():
        sub_env_map: Mapping[str, str] = fetch_env_map_from_group(env_map, sub_group)
        env_map = _cascade_env_map(env_map, sub_env_map)
    return env_map


@typechecked
def fetch_env_map_from_task(env_map: Mapping[str, str], task: AnyTask):
    task_env_map: Mapping[str, str] = {}
    for env_file in task._get_env_files():
        envs = env_file.get_envs()
        task_env_map = _add_envs_to_env_map(task_env_map, envs)
    task_env_map = _add_envs_to_env_map(task_env_map, task._envs)
    env_map = _cascade_env_map(env_map, task_env_map)
    for upstream in task._get_upstreams():
        task_env_map = fetch_env_map_from_task(env_map, upstream)
    for checker in task._get_checkers():
        task_env_map = fetch_env_map_from_task(env_map, checker)
    return env_map


@typechecked
def _add_envs_to_env_map(
    env_map: Mapping[str, str], envs: List[Env]
) -> Mapping[str, str]:
    for env in envs:
        if env.get_os_name() == "":
            continue
        env_name = _get_env_name(env)
        env_default = _get_env_default(env)
        env_map[env_name] = env_default
    return env_map


@typechecked
def _cascade_env_map(
    env_map: Mapping[str, str], other_env_map: Mapping[str, str]
) -> Mapping[str, str]:
    for key, value in other_env_map.items():
        if key in env_map:
            continue
        env_map[key] = value
    return env_map


@typechecked
def _get_env_name(env: Env) -> str:
    if env.get_os_name() is None:
        return env.get_name()
    return env.get_os_name()


@typechecked
def _get_env_default(env: Env) -> str:
    if is_probably_jinja(env.get_default()):
        return ""
    return env.get_default()
