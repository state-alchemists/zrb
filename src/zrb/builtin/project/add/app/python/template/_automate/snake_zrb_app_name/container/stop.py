from zrb import DockerComposeTask, runner

from ..._project import stop_project_containers
from .._constant import RESOURCE_DIR
from ..image._env import image_env
from ._env import compose_env_file, host_port_env
from ._group import snake_zrb_app_name_container_group
from ._service_config import snake_zrb_app_name_service_config

stop_snake_zrb_app_name_container = DockerComposeTask(
    icon="⛔",
    name="stop",
    description="Stop human readable zrb app name container",
    group=snake_zrb_app_name_container_group,
    cwd=RESOURCE_DIR,
    compose_cmd="stop",
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs={"snake_zrb_app_name": snake_zrb_app_name_service_config},
    env_files=[compose_env_file],
    envs=[
        image_env,
        host_port_env,
    ],
)

stop_snake_zrb_app_name_container >> stop_project_containers

runner.register(stop_snake_zrb_app_name_container)
