from zrb import DockerComposeTask, runner
from zrb.builtin.group import project_group

from ._checker import (
    app_container_checker,
    kafka_outside_checker,
    kafka_plaintext_checker,
    pandaproxy_outside_checker,
    pandaproxy_plaintext_checker,
    rabbitmq_checker,
    rabbitmq_management_checker,
    redpanda_console_checker,
)
from ._config import RESOURCE_DIR, SERVICE_CONFIGS
from ._env import app_enable_otel_env, image_env
from ._env_file import compose_env_file
from ._helper import (
    activate_all_compose_profile,
    activate_selected_compose_profile,
    should_start_container,
)
from ._input import (
    enable_monitoring_input,
    host_input,
    https_input,
    image_input,
    local_input,
    run_mode_input,
)
from .image import build_snake_zrb_app_name_image

###############################################################################
# ⚙️ remove-kebab-zrb-task-name-container
###############################################################################

remove_snake_zrb_app_name_container = DockerComposeTask(
    icon="💨",
    name="remove-kebab-zrb-app-name-container",
    description="Remove human readable zrb app name container",
    group=project_group,
    cwd=RESOURCE_DIR,
    setup_cmd=activate_all_compose_profile,
    compose_cmd="down",
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs=SERVICE_CONFIGS,
    envs=[image_env],
    env_files=[compose_env_file],
)
runner.register(remove_snake_zrb_app_name_container)

###############################################################################
# ⚙️ init-kebab-zrb-task-name-container
###############################################################################

init_snake_zrb_app_name_container = DockerComposeTask(
    icon="🔥",
    name="init-kebab-zrb-app-name-container",
    group=project_group,
    inputs=[
        local_input,
        enable_monitoring_input,
        run_mode_input,
        host_input,
        image_input,
    ],
    should_execute=should_start_container,
    upstreams=[build_snake_zrb_app_name_image, remove_snake_zrb_app_name_container],
    cwd=RESOURCE_DIR,
    setup_cmd=activate_selected_compose_profile,
    compose_cmd="up",
    compose_flags=["-d"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs=SERVICE_CONFIGS,
    envs=[
        image_env,
        app_enable_otel_env,
    ],
    env_files=[compose_env_file],
)

###############################################################################
# ⚙️ start-kebab-zrb-task-name-container
###############################################################################

start_snake_zrb_app_name_container = DockerComposeTask(
    icon="🐳",
    name="start-kebab-zrb-app-name-container",
    description="Start human readable zrb app name container",
    group=project_group,
    inputs=[
        local_input,
        run_mode_input,
        host_input,
        https_input,
        image_input,
    ],
    should_execute=should_start_container,
    upstreams=[init_snake_zrb_app_name_container],
    cwd=RESOURCE_DIR,
    setup_cmd=activate_selected_compose_profile,
    compose_cmd="logs",
    compose_flags=["-f"],
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs=SERVICE_CONFIGS,
    envs=[image_env],
    env_files=[compose_env_file],
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
runner.register(start_snake_zrb_app_name_container)

###############################################################################
# ⚙️ stop-kebab-zrb-task-name-container
###############################################################################

stop_snake_zrb_app_name_container = DockerComposeTask(
    icon="⛔",
    name="stop-kebab-zrb-app-name-container",
    description="Stop human readable zrb app name container",
    group=project_group,
    cwd=RESOURCE_DIR,
    setup_cmd=activate_all_compose_profile,
    compose_cmd="stop",
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs=SERVICE_CONFIGS,
    envs=[image_env],
    env_files=[compose_env_file],
)
runner.register(stop_snake_zrb_app_name_container)
