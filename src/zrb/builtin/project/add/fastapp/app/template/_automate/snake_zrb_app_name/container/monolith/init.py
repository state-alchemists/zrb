from zrb import DockerComposeTask

from ..._constant import RESOURCE_DIR
from ..._input import host_input, local_input
from ...image import build_snake_zrb_app_name_image
from ...image._env import image_env
from ...image._input import image_input
from .._env import compose_env_file, host_port_env
from .._input import enable_monitoring_input
from .._service_config import snake_zrb_app_name_service_configs
from ..remove import remove_snake_zrb_app_name_container
from ._helper import activate_monolith_compose_profile

init_snake_zrb_app_name_monolith_container = DockerComposeTask(
    icon="🔥",
    name="init-kebab-zrb-app-name-monolith-container",
    inputs=[
        local_input,
        enable_monitoring_input,
        host_input,
        image_input,
    ],
    should_execute="{{ input.local_snake_zrb_app_name}}",
    upstreams=[build_snake_zrb_app_name_image, remove_snake_zrb_app_name_container],
    cwd=RESOURCE_DIR,
    setup_cmd=activate_monolith_compose_profile,
    compose_cmd="up",
    compose_flags=["-d"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs=snake_zrb_app_name_service_configs,
    env_files=[compose_env_file],
    envs=[
        image_env,
        host_port_env,
    ],
)
