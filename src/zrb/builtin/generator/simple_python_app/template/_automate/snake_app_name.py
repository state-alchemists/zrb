from zrb import (
    DockerComposeTask, HTTPChecker, Env, runner
)
from zrb.builtin._group import project_group
import os

current_dir = os.path.dirname(__file__)
resource_dir = os.path.abspath(os.path.join(
    current_dir, '..', 'src', 'kebab-app-name'
))


start_snake_app_name_container = DockerComposeTask(
    name='start-kebab-app-name-container',
    description='Start human readable app name container',
    group=project_group,
    cwd=resource_dir,
    compose_cmd='up',
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
        HTTPChecker(port='{{env.HOST_PORT}}')
    ]
)
runner.register(start_snake_app_name_container)
