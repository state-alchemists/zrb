from zrb import DockerComposeTask, HTTPChecker, Env, runner
from zrb.builtin._group import project_group
import os

###############################################################################
# Constants
###############################################################################

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
RESOURCE_DIR = os.path.join(PROJECT_DIR, 'src', 'kebab-task-name')

###############################################################################
# Task Definitions
###############################################################################

snake_task_name = DockerComposeTask(
    name='kebab-task-name',
    description='human readable task name',
    group=project_group,
    cwd=RESOURCE_DIR,
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
            default='httpPort'
        ),
    ],
    checkers=[
        HTTPChecker(
            name='check-kebab-app-name',
            port='{{env.HOST_PORT}}'
        )
    ]
)
runner.register(snake_task_name)
