from zrb import DockerComposeTask, Env, HTTPChecker, runner
from zrb.builtin._group import project_group
from ._common import (
    RESOURCE_DIR,
    local_input, host_input, https_input, image_input,
    image_env
)
from .image import build_snake_app_name_image

compose_env_prefix = 'CONTAINER_ENV_PREFIX'
compose_envs = [
    image_env,
    Env(
        name='HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_HOST_PORT',
        default='httpPort'
    ),
]

###############################################################################
# Task Definitions
###############################################################################

remove_snake_app_name_container = DockerComposeTask(
    icon='💨',
    name='remove-kebab-app-name-container',
    description='Rumove human readable app name container',
    group=project_group,
    cwd=RESOURCE_DIR,
    compose_cmd='down',
    compose_env_prefix=compose_env_prefix,
    envs=compose_envs,
)
runner.register(remove_snake_app_name_container)

stop_snake_app_name_container = DockerComposeTask(
    icon='⛔',
    name='stop-kebab-app-name-container',
    description='Stop human readable app name container',
    group=project_group,
    cwd=RESOURCE_DIR,
    compose_cmd='stop',
    compose_env_prefix=compose_env_prefix,
    envs=compose_envs,
)
runner.register(stop_snake_app_name_container)

start_snake_app_name_container = DockerComposeTask(
    icon='🐳',
    name='start-kebab-app-name-container',
    description='Start human readable app name container',
    group=project_group,
    inputs=[
        local_input,
        host_input,
        https_input,
        image_input,
    ],
    skip_execution='{{not input.local_snake_app_name}}',
    upstreams=[
        build_snake_app_name_image,
        remove_snake_app_name_container
    ],
    cwd=RESOURCE_DIR,
    compose_cmd='up',
    compose_env_prefix=compose_env_prefix,
    envs=compose_envs,
    checkers=[
        HTTPChecker(
            name='check-kebab-app-name',
            host='{{input.snake_app_name_host}}',
            port='{{env.HOST_PORT}}',
            is_https='{{input.snake_app_name_https}}'
        )
    ]
)
runner.register(start_snake_app_name_container)
