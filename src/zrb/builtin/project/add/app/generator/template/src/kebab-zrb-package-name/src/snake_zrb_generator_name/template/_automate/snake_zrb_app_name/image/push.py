from zrb import DockerComposeTask, runner

from ..._project import publish_project, push_project_images
from .._constant import RESOURCE_DIR
from .._input import local_input
from ._env import image_env
from ._group import snake_zrb_app_name_image_group
from ._input import image_input
from .build import build_snake_zrb_app_name_image

push_snake_zrb_app_name_image = DockerComposeTask(
    icon="📰",
    name="push",
    description="Push human readable zrb app name image",
    group=snake_zrb_app_name_image_group,
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

push_snake_zrb_app_name_image >> push_project_images
push_snake_zrb_app_name_image >> publish_project

runner.register(push_snake_zrb_app_name_image)
