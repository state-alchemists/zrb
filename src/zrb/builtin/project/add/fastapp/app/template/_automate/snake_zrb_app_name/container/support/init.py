from zrb import DockerComposeTask

from ..._constant import RESOURCE_DIR
from ..._input import host_input, local_input
from ...image._input import image_input
from .._env import compose_env_file
from ..remove import remove_snake_zrb_app_name_container
from ._helper import activate_support_compose_profile, should_start_support_container

init_snake_zrb_app_name_support_container = DockerComposeTask(
    icon="🔥",
    name="init-kebab-zrb-app-name-support-container",
    inputs=[
        local_input,
        host_input,
        image_input,
    ],
    should_execute=should_start_support_container,
    upstreams=[remove_snake_zrb_app_name_container],
    cwd=RESOURCE_DIR,
    setup_cmd=activate_support_compose_profile,
    compose_cmd="up",
    compose_flags=["-d"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    env_files=[compose_env_file],
)
