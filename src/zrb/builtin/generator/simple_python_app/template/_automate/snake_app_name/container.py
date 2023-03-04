from zrb import (
    DockerComposeTask, Env, HTTPChecker, runner
)
from zrb.builtin._group import project_group
from .common import (
    local_snake_app_name_input, snake_app_name_host_input,
    snake_app_name_https_input
)
import os

current_dir = os.path.dirname(__file__)
resource_dir = os.path.abspath(os.path.join(
    current_dir, '..', '..', 'src', 'kebab-app-name'
))
template_env_file = os.path.join(resource_dir, 'src', 'template.env')

env_prefix = 'CONTAINER_ENV_PREFIX'
envs = [
    Env(
        name='HOST_PORT',
        os_name='CONTAINER_ENV_PREFIX_HOST_PORT',
        default='httpPort'
    ),
]

build_snake_app_name_image = DockerComposeTask(
    name='build-kebab-app-name-image',
    description='Build human readable app name image',
    group=project_group,
    inputs=[local_snake_app_name_input],
    skip_execution='{{not input.local_snake_app_name}}',
    cwd=resource_dir,
    compose_cmd='build',
    compose_flags=[
        '--no-cache'
    ],
    compose_env_prefix=env_prefix,
    envs=envs,
)
runner.register(build_snake_app_name_image)

push_snake_app_name_image = DockerComposeTask(
    name='push-kebab-app-name-image',
    description='Push human readable app name image',
    group=project_group,
    upstreams=[build_snake_app_name_image],
    cwd=resource_dir,
    compose_cmd='push',
    compose_env_prefix=env_prefix,
    envs=envs,
)
runner.register(push_snake_app_name_image)

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
        snake_app_name_https_input
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
