import os

from zrb import DockerComposeTask, Env, EnvFile, HTTPChecker, runner
from zrb.builtin import project_group

_CURRENT_DIR = os.path.dirname(__file__)
_PROJECT_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
_RESOURCE_DIR = os.path.join(_PROJECT_DIR, "src", "kebab-zrb-task-name")

snake_zrb_task_name = DockerComposeTask(
    name="kebab-zrb-task-name",
    description="human readable zrb task name",
    group=project_group,
    cwd=_RESOURCE_DIR,
    compose_cmd="zrbComposeCommand",
    compose_env_prefix="ZRB_ENV_PREFIX",
    env_files=[
        EnvFile(
            path=os.path.join(_RESOURCE_DIR, "docker-compose.env"),
            prefix="ZRB_ENV_PREFIX",
        )
    ],
    envs=[
        Env(
            name="HOST_PORT", os_name="ZRB_ENV_PREFIX_HOST_PORT", default="zrbHttpPort"
        ),
    ],
    checkers=[HTTPChecker(name="check-kebab-zrb-task-name", port="{{env.HOST_PORT}}")],
)
runner.register(snake_zrb_task_name)
