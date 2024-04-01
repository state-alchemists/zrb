from zrb import DockerComposeTask, runner

from ..._checker import (
    kafka_outside_checker,
    kafka_plaintext_checker,
    pandaproxy_outside_checker,
    pandaproxy_plaintext_checker,
    rabbitmq_checker,
    rabbitmq_management_checker,
    redpanda_console_checker,
)
from ..._constant import RESOURCE_DIR
from ..._input import host_input, https_input, local_input
from ...image._input import image_input
from .._env import compose_env_file
from .._input import enable_monitoring_input
from .._service_config import snake_zrb_app_name_service_configs
from ._group import snake_zrb_app_name_support_container_group
from ._helper import activate_support_compose_profile, should_start_support_container
from .init import init_snake_zrb_app_name_support_container

start_snake_zrb_app_name_support_container = DockerComposeTask(
    icon="🐳",
    name="start",
    description="Start human readable zrb app name container",
    group=snake_zrb_app_name_support_container_group,
    inputs=[
        local_input,
        enable_monitoring_input,
        host_input,
        https_input,
        image_input,
    ],
    should_execute=should_start_support_container,
    upstreams=[init_snake_zrb_app_name_support_container],
    cwd=RESOURCE_DIR,
    setup_cmd=activate_support_compose_profile,
    compose_cmd="logs",
    compose_flags=["-f"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs=snake_zrb_app_name_service_configs,
    env_files=[compose_env_file],
    checkers=[
        rabbitmq_checker,
        rabbitmq_management_checker,
        kafka_outside_checker,
        kafka_plaintext_checker,
        redpanda_console_checker,
        pandaproxy_outside_checker,
        pandaproxy_plaintext_checker,
    ],
)

runner.register(start_snake_zrb_app_name_support_container)
