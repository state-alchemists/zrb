import os

from zrb import DockerComposeTask, Env, EnvFile, HTTPChecker, runner
from zrb.builtin.group import project_group

###############################################################################
# 🏔️ Constants
###############################################################################

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
RESOURCE_DIR = os.path.join(PROJECT_DIR, "src", "kebab-zrb-task-name")

###############################################################################
# ⚙️ kebab-zrb-task-name
###############################################################################

snake_zrb_task_name = DockerComposeTask(
    name="kebab-zrb-task-name",
    description="human readable zrb task name",
    group=project_group,
    cwd=RESOURCE_DIR,
    compose_cmd="zrbComposeCommand",
    compose_env_prefix="ZRB_ENV_PREFIX",
    env_files=[
        EnvFile(
            path=os.path.join(RESOURCE_DIR, "docker-compose.env"),
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
