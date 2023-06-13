from zrb import DockerComposeTask, Env, StrInput, runner
from zrb.builtin._group import project_group
from ._common import RESOURCE_DIR, local_input

###############################################################################
# Input Definitions
###############################################################################

image_input = StrInput(
    name='kebab-app-name-image',
    description='Image name of "kebab-app-name"',
    prompt='Image name of "kebab-app-name"',
    default='app-image-name:latest'
)

###############################################################################
# Env fDefinitions
###############################################################################

image_env = Env(
    name='IMAGE',
    os_name='CONTAINER_ENV_PREFIX_IMAGE',
    default='{{input.snake_app_name_image}}'
)

###############################################################################
# Task Definitions
###############################################################################

build_snake_app_name_image = DockerComposeTask(
    icon='🏭',
    name='build-kebab-app-name-image',
    description='Build human readable app name image',
    group=project_group,
    inputs=[
        local_input,
        image_input,
    ],
    envs=[image_env],
    skip_execution='{{not input.local_snake_app_name}}',
    cwd=RESOURCE_DIR,
    compose_cmd='build',
    compose_args=[
        'kebab-app-name'
    ],
    compose_env_prefix='CONTAINER_ENV_PREFIX',
)
runner.register(build_snake_app_name_image)

push_snake_app_name_image = DockerComposeTask(
    icon='📰',
    name='push-kebab-app-name-image',
    description='Push human readable app name image',
    group=project_group,
    inputs=[
        local_input,
        image_input,
    ],
    envs=[image_env],
    upstreams=[build_snake_app_name_image],
    cwd=RESOURCE_DIR,
    compose_cmd='push',
    compose_args=[
        'kebab-app-name'
    ],
    compose_env_prefix='CONTAINER_ENV_PREFIX',
)
runner.register(push_snake_app_name_image)
