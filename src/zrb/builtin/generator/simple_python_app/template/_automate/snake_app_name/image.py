from zrb import (
    DockerComposeTask, runner
)
from zrb.builtin._group import project_group
from .common import local_snake_app_name_input
import os

current_dir = os.path.dirname(__file__)
resource_dir = os.path.abspath(os.path.join(
    current_dir, '..', '..', 'src', 'kebab-app-name'
))
template_env_file = os.path.join(resource_dir, 'src', 'template.env')

env_prefix = 'CONTAINER_ENV_PREFIX'

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
)
runner.register(push_snake_app_name_image)

