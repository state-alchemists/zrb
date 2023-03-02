from zrb import (
    DockerComposeTask, HTTPChecker, Env, runner
)
from zrb.builtin._group import project_group
import os

current_dir = os.path.dirname(__file__)
resource_dir = os.path.abspath(os.path.join(
    current_dir, '..', '..', 'src', 'kebab-app-name'
))

compose_envs = [
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
]

start_snake_app_name_container = DockerComposeTask(
    name='start-kebab-app-name-container',
    description='Start human readable app name container',
    group=project_group,
    cwd=resource_dir,
    compose_cmd='up',
    compose_env_prefix='ENV_PREFIX',
    envs=compose_envs,
    checkers=[
        HTTPChecker(port='{{env.HOST_PORT}}')
    ]
)
runner.register(start_snake_app_name_container)

stop_snake_app_name_container = DockerComposeTask(
    name='stop-kebab-app-name-container',
    description='Stop human readable app name container',
    group=project_group,
    cwd=resource_dir,
    compose_cmd='stop',
    compose_env_prefix='ENV_PREFIX',
    envs=compose_envs,
)
runner.register(stop_snake_app_name_container)

remove_snake_app_name_container = DockerComposeTask(
    name='remove-kebab-app-name-container',
    description='Rumove human readable app name container',
    group=project_group,
    cwd=resource_dir,
    compose_cmd='down',
    compose_env_prefix='ENV_PREFIX',
    envs=compose_envs,
)
runner.register(remove_snake_app_name_container)

build_snake_app_name_image = DockerComposeTask(
    name='build-kebab-app-name-image',
    description='Build human readable app name image',
    group=project_group,
    cwd=resource_dir,
    compose_cmd='build',
    compose_env_prefix='ENV_PREFIX',
    envs=compose_envs,
)
runner.register(build_snake_app_name_image)

push_snake_app_name_image = DockerComposeTask(
    name='push-kebab-app-name-image',
    description='Push human readable app name image',
    group=project_group,
    cwd=resource_dir,
    compose_cmd='push',
    compose_env_prefix='ENV_PREFIX',
    envs=compose_envs,
)
runner.register(push_snake_app_name_image)
