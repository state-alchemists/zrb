from zrb import DockerComposeTask, HTTPChecker, runner

from ..._project import start_project_containers
from .._constant import RESOURCE_DIR
from .._input import host_input, https_input, local_input
from ..image._env import image_env
from ..image._input import image_input
from ._env import compose_env_file, host_port_env
from ._group import snake_zrb_app_name_container_group
from ._service_config import snake_zrb_app_name_service_config
from .init import init_snake_zrb_app_name_container

start_snake_zrb_app_name_container = DockerComposeTask(
    icon="🐳",
    name="start",
    description="Start human readable zrb app name container",
    group=snake_zrb_app_name_container_group,
    inputs=[
        local_input,
        host_input,
        https_input,
        image_input,
    ],
    should_execute="{{ input.local_snake_zrb_app_name}}",
    upstreams=[init_snake_zrb_app_name_container],
    cwd=RESOURCE_DIR,
    compose_cmd="logs",
    compose_flags=["-f"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs={"snake_zrb_app_name": snake_zrb_app_name_service_config},
    env_files=[compose_env_file],
    envs=[
        image_env,
        host_port_env,
    ],
    checkers=[
        HTTPChecker(
            name="check-kebab-zrb-app-name",
            host="{{input.snake_zrb_app_name_host}}",
            port="{{env.HOST_PORT}}",
            is_https="{{input.snake_zrb_app_name_https}}",
        )
    ],
)

start_snake_zrb_app_name_container >> start_project_containers

runner.register(start_snake_zrb_app_name_container)
