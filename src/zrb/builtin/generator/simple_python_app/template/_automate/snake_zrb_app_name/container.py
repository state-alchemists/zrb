import os

from zrb import DockerComposeTask, Env, EnvFile, HTTPChecker, ServiceConfig, runner
from zrb.builtin.group import project_group

from ._common import APP_DIR, RESOURCE_DIR, host_input, https_input, local_input
from .image import build_snake_zrb_app_name_image, image_env, image_input

###############################################################################
# 🌳 Env File Definitions
###############################################################################

compose_env_file = EnvFile(
    path=os.path.join(RESOURCE_DIR, "docker-compose.env"),
    prefix="CONTAINER_ZRB_ENV_PREFIX",
)

###############################################################################
# 🌱 Env Definitions
###############################################################################

host_port_env = Env(
    name="HOST_PORT",
    os_name="CONTAINER_ZRB_ENV_PREFIX_HOST_PORT",
    default="zrbAppHttpPort",
)

###############################################################################
# Service Config Definitions
###############################################################################

snake_zrb_app_name_service_config = ServiceConfig(
    env_files=[
        EnvFile(
            path=os.path.join(APP_DIR, "template.env"),
            prefix="CONTAINER_ZRB_ENV_PREFIX",
        )
    ]
)

###############################################################################
# ⚙️ kebab-zrb-task-name
###############################################################################

remove_snake_zrb_app_name_container = DockerComposeTask(
    icon="💨",
    name="remove-kebab-zrb-app-name-container",
    description="Remove human readable zrb app name container",
    group=project_group,
    cwd=RESOURCE_DIR,
    compose_cmd="down",
    compose_env_prefix="CONTAINER_ZRB_ENV_PREFIX",
    compose_service_configs={"snake_zrb_app_name": snake_zrb_app_name_service_config},
    env_files=[compose_env_file],
    envs=[
        image_env,
        host_port_env,
    ],
)
runner.register(remove_snake_zrb_app_name_container)

###############################################################################
# ⚙️ kebab-zrb-task-name
###############################################################################

stop_snake_zrb_app_name_container = DockerComposeTask(
    icon="⛔",
    name="stop-kebab-zrb-app-name-container",
    description="Stop human readable zrb app name container",
    group=project_group,
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
runner.register(stop_snake_zrb_app_name_container)

###############################################################################
# ⚙️ kebab-zrb-task-name
###############################################################################

init_snake_zrb_app_name_container = DockerComposeTask(
    icon="🔥",
    name="init-kebab-zrb-app-name-container",
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

###############################################################################
# ⚙️ kebab-zrb-task-name
###############################################################################

start_snake_zrb_app_name_container = DockerComposeTask(
    icon="🐳",
    name="start-kebab-zrb-app-name-container",
    description="Start human readable zrb app name container",
    group=project_group,
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
runner.register(start_snake_zrb_app_name_container)
