from zrb import (
    DockerComposeTask, Env, HTTPChecker, runner
)
from zrb.builtin._group import project_group
from .common import (
    local_snake_app_name_input, snake_app_name_host_input,
    snake_app_name_https_input,
    snake_app_name_image_input, snake_app_name_image_env
)
from .image import build_snake_app_name_image
import os

current_dir = os.path.dirname(__file__)
resource_dir = os.path.abspath(os.path.join(
    current_dir, '..', '..', 'src', 'kebab-app-name'
))
template_env_file = os.path.join(resource_dir, 'src', 'template.env')

env_prefix = 'CONTAINER_ENV_PREFIX'
envs = [
    snake_app_name_image_env,
    Env(
        name='HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_HOST_PORT',
        default='httpPort'
    ),
]

remove_snake_app_name_container = DockerComposeTask(
    name='remove-kebab-app-name-container',
    description='Rumove human readable app name container',
    group=project_group,
    cwd=resource_dir,
    compose_cmd='down',
    compose_env_prefix=env_prefix,
    envs=envs,
)
runner.register(remove_snake_app_name_container)

start_snake_app_name_container = DockerComposeTask(
    name='start-kebab-app-name-container',
    description='Start human readable app name container',
    group=project_group,
    inputs=[
        local_snake_app_name_input,
        snake_app_name_host_input,
        snake_app_name_https_input,
        snake_app_name_image_input,
    ],
    skip_execution='{{not input.local_snake_app_name}}',
    upstreams=[
        build_snake_app_name_image,
        remove_snake_app_name_container
    ],
    cwd=resource_dir,
    compose_cmd='up',
    compose_env_prefix=env_prefix,
    envs=envs,
    checkers=[
        HTTPChecker(
            host='{{input.snake_app_name_host}}',
            port='{{env.APP_PORT}}',
            is_https='{{input.snake_app_name_https}}'
        )
    ]
)
runner.register(start_snake_app_name_container)

stop_snake_app_name_container = DockerComposeTask(
    name='stop-kebab-app-name-container',
    description='Stop human readable app name container',
    group=project_group,
    cwd=resource_dir,
    compose_cmd='stop',
    compose_env_prefix=env_prefix,
    envs=envs,
)
runner.register(stop_snake_app_name_container)
