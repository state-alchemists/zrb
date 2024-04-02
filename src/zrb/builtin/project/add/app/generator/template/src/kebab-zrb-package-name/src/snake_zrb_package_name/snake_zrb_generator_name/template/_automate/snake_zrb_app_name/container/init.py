from zrb import DockerComposeTask

from .._constant import RESOURCE_DIR
from .._input import host_input, local_input
from ..image import build_snake_zrb_app_name_image
from ..image._env import image_env
from ..image._input import image_input
from ._env import compose_env_file, host_port_env
from ._group import snake_zrb_app_name_container_group
from ._service_config import snake_zrb_app_name_service_config
from .remove import remove_snake_zrb_app_name_container

init_snake_zrb_app_name_container = DockerComposeTask(
    icon="🔥",
    name="init",
    group=snake_zrb_app_name_container_group,
    inputs=[
        local_input,
        host_input,
        image_input,
    ],
    should_execute="{{ input.local_snake_zrb_app_name}}",
    upstreams=[build_snake_zrb_app_name_image, remove_snake_zrb_app_name_container],
    cwd=RESOURCE_DIR,
    compose_cmd="up",
    compose_flags=["-d"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs={"snake_zrb_app_name": snake_zrb_app_name_service_config},
    env_files=[compose_env_file],
    envs=[
        image_env,
        host_port_env,
    ],
)
