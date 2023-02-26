from zrb import (
    DockerComposeTask, HTTPChecker, Env, runner
)
from zrb.builtin._group import project_group
import os

current_dir = os.path.dirname(__file__)
resource_dir = os.path.abspath(os.path.join(
    current_dir, '..', 'src', 'kebab-task-name')
)


snake_task_name = DockerComposeTask(
    name='kebab-task-name',
    description='human readable task name',
    group=project_group,
    cwd=resource_dir,
    compose_cmd='composeCommand',
    compose_env_prefix='ENV_PREFIX',
    envs=[
        Env(
            name='MESSAGE',
            os_name='ENV_PREFIX_MESSAGE',
            default='Salve Mane'
        ),
        Env(
            name='CONTAINER_PORT',
            os_name='ENV_PREFIX_CONTAINER_PORT',
            default='3000'
        ),
        Env(
            name='HOST_PORT',
            os_name='ENV_PREFIX_HOST_PORT',
            default='3000'
        ),
    ],
    checkers=[
        HTTPChecker(port='{{env.HOST_PORT}}')
    ]
)
runner.register(snake_task_name)
