from zrb import DockerComposeTask, runner

from ..._project import build_project, build_project_images
from .._constant import RESOURCE_DIR
from .._input import local_input
from ._env import image_env
from ._group import snake_zrb_app_name_image_group
from ._input import image_input

build_snake_zrb_app_name_image = DockerComposeTask(
    icon="🏭",
    name="build",
    description="Build human readable zrb app name image",
    group=snake_zrb_app_name_image_group,
    inputs=[
        local_input,
        image_input,
    ],
    envs=[image_env],
    should_execute="{{ input.local_snake_zrb_app_name}}",
    cwd=RESOURCE_DIR,
    compose_cmd="build",
    compose_flags=["--no-cache"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
)

build_snake_zrb_app_name_image >> build_project_images
build_snake_zrb_app_name_image >> build_project

runner.register(build_snake_zrb_app_name_image)
