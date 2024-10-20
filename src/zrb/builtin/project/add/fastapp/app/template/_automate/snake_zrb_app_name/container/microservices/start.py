from zrb import DockerComposeTask, runner

from ...._project import start_project_containers
from ..._checker import (
    app_container_checker,
    kafka_outside_checker,
    kafka_plaintext_checker,
    pandaproxy_outside_checker,
    pandaproxy_plaintext_checker,
    rabbitmq_checker,
    rabbitmq_management_checker,
    redpanda_console_checker,
)
from ..._constant import PREFER_MICROSERVICES, RESOURCE_DIR
from ..._input import host_input, https_input, local_input
from ...image import build_snake_zrb_app_name_image
from ...image._env import image_env
from ...image._input import image_input
from .._env import compose_env_file, host_port_env
from .._input import enable_monitoring_input
from .._service_config import snake_zrb_app_name_service_configs
from ..remove import remove_snake_zrb_app_name_container
from ._group import snake_zrb_app_name_microservices_container_group

start_snake_zrb_app_name_microservices_container = DockerComposeTask(
    icon="🐳",
    name="start",
    description="Start human readable zrb app name container",
    group=snake_zrb_app_name_microservices_container_group,
    inputs=[
        local_input,
        enable_monitoring_input,
        host_input,
        https_input,
        image_input,
    ],
    should_execute="{{ input.local_snake_zrb_app_name}}",
    upstreams=[build_snake_zrb_app_name_image, remove_snake_zrb_app_name_container],
    cwd=RESOURCE_DIR,
    template_path="docker-compose.template.yml",
    compose_start=True,
    compose_profiles=[
        '{{"postgres" if env.APP_DB_CONNECTION.startswith("postgresql") else ""}}',
        '{{"kafka" if env.APP_BROKER_TYPE == "kafka" else ""}}',
        '{{"rabbitmq" if env.APP_BROKER_TYPE == "rabbitmq" else ""}}',
        '{{"monitoring" if input.enable_snake_zrb_app_name_monitoring else ""}}',
        "microservices",
    ],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs=snake_zrb_app_name_service_configs,
    env_files=[compose_env_file],
    envs=[
        image_env,
        host_port_env,
    ],
    checkers=[
        app_container_checker,
        rabbitmq_checker,
        rabbitmq_management_checker,
        kafka_outside_checker,
        kafka_plaintext_checker,
        redpanda_console_checker,
        pandaproxy_outside_checker,
        pandaproxy_plaintext_checker,
    ],
)

if PREFER_MICROSERVICES:
    start_snake_zrb_app_name_microservices_container >> start_project_containers

runner.register(start_snake_zrb_app_name_microservices_container)
