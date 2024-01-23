from zrb import DockerComposeTask, Env, StrInput, runner
from zrb.builtin.group import project_group

from ._common import RESOURCE_DIR, local_input

###############################################################################
# 🔤 Input Definitions
###############################################################################

image_input = StrInput(
    name="kebab-zrb-app-name-image",
    description='Image name of "kebab-zrb-app-name"',
    prompt='Image name of "kebab-zrb-app-name"',
    default="zrb-app-image-name:latest",
)


###############################################################################
# 🌱 Env Definitions
###############################################################################

image_env = Env(
    name="IMAGE",
    os_name="CONTAINER_ZRB_ENV_PREFIX_IMAGE",
    default="{{input.snake_zrb_app_name_image}}",
)

###############################################################################
# ⚙️ build-zrb-task-name-image
###############################################################################

build_snake_zrb_app_name_image = DockerComposeTask(
    icon="🏭",
    name="build-kebab-zrb-app-name-image",
    description="Build human readable zrb app name image",
    group=project_group,
    inputs=[
        local_input,
        image_input,
    ],
    envs=[image_env],
    should_execute="{{input.local_snake_zrb_app_name}}",
    cwd=RESOURCE_DIR,
    compose_cmd="build",
    compose_flags=["--no-cache"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
)
runner.register(build_snake_zrb_app_name_image)

###############################################################################
# ⚙️ push-zrb-task-name-image
###############################################################################

push_snake_zrb_app_name_image = DockerComposeTask(
    icon="📰",
    name="push-kebab-zrb-app-name-image",
    description="Push human readable zrb app name image",
    group=project_group,
    inputs=[
        local_input,
        image_input,
    ],
    envs=[image_env],
    upstreams=[build_snake_zrb_app_name_image],
    cwd=RESOURCE_DIR,
    compose_cmd="push",
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
)
runner.register(push_snake_zrb_app_name_image)
