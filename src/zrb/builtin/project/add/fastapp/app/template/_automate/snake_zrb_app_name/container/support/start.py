from zrb import DockerComposeStartTask, runner

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
from ..remove import remove_snake_zrb_app_name_container
from ._group import snake_zrb_app_name_support_container_group

start_snake_zrb_app_name_support_container = DockerComposeStartTask(
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
    upstreams=[remove_snake_zrb_app_name_container],
    cwd=RESOURCE_DIR,
    should_execute=" ".join(
        [
            "{{",
            'env.APP_DB_CONNECTION.startswith("postgresql")',
            'or env.APP_BROKER_TYPE in ("kafka", "rabbitmq")',
            "or input.enable_snake_zrb_app_name_monitoring",
            "}}",
        ]
    ),
    compose_profiles=[
        '{{"postgres" if env.APP_DB_CONNECTION.startswith("postgresql") else ""}}',
        '{{"kafka" if env.APP_BROKER_TYPE == "kafka" else ""}}',
        '{{"rabbitmq" if env.APP_BROKER_TYPE == "rabbitmq" else ""}}',
        '{{"monitoring" if input.enable_snake_zrb_app_name_monitoring else ""}}',
    ],
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
