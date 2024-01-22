from zrb import DockerComposeTask, runner
from zrb.builtin.group import project_group
from ._config import RESOURCE_DIR
from ._input import local_input, image_input
from ._env import image_env

###############################################################################
# ⚙️ build-kebab-zrb-task-name-image
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
    should_execute="{{ input.local_snake_zrb_app_name}}",
    cwd=RESOURCE_DIR,
    compose_cmd="build",
    compose_args=["kebab-zrb-app-name"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
)
runner.register(build_snake_zrb_app_name_image)

###############################################################################
# ⚙️ push-kebab-zrb-task-name-image
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
    compose_args=["kebab-zrb-app-name"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
)
runner.register(push_snake_zrb_app_name_image)
