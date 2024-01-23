import os

from zrb import CmdTask, DockerComposeTask, Env, Task, runner
from zrb.builtin.group import project_group

from ._checker import (
    app_local_checker,
    kafka_outside_checker,
    kafka_plaintext_checker,
    pandaproxy_outside_checker,
    pandaproxy_plaintext_checker,
    rabbitmq_checker,
    rabbitmq_management_checker,
    redpanda_console_checker,
)
from ._config import APP_DIR, CURRENT_DIR, RESOURCE_DIR
from ._env import app_enable_otel_env
from ._env_file import app_env_file
from ._get_start_microservices import get_start_microservices
from ._helper import (
    activate_support_compose_profile,
    should_start_local_microservices,
    should_start_local_monolith,
    should_start_support_container,
)
from ._input import (
    enable_monitoring_input,
    host_input,
    https_input,
    image_input,
    local_input,
    run_mode_input,
)
from .container import compose_env_file, remove_snake_zrb_app_name_container
from .frontend import build_snake_zrb_app_name_frontend

###############################################################################
# ⚙️ init-kebab-zrb-task-name-support-container
###############################################################################

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

###############################################################################
# ⚙️ start-kebab-zrb-task-name-support-container
###############################################################################

start_snake_zrb_app_name_support_container = DockerComposeTask(
    icon="🐳",
    name="start-kebab-zrb-app-name-support-container",
    description="Start human readable zrb app name container",
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

###############################################################################
# ⚙️ prepare-kebab-zrb-task-name-backend
###############################################################################

prepare_snake_zrb_app_name_backend = CmdTask(
    icon="🚤",
    name="prepare-kebab-zrb-app-name-backend",
    description="Prepare backend for human readable zrb app name",
    group=project_group,
    cwd=APP_DIR,
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "activate-venv.sh"),
        os.path.join(CURRENT_DIR, "cmd", "app-prepare-backend.sh"),
    ],
)
runner.register(prepare_snake_zrb_app_name_backend)

###############################################################################
# ⚙️ start-monolith-kebab-zrb-task-name
###############################################################################

start_monolith_snake_zrb_app_name = CmdTask(
    icon="🚤",
    name="start-monolith-kebab-zrb-app-name",
    inputs=[
        local_input,
        enable_monitoring_input,
        run_mode_input,
        host_input,
        https_input,
    ],
    should_execute=should_start_local_monolith,
    upstreams=[
        start_snake_zrb_app_name_support_container,
        build_snake_zrb_app_name_frontend,
        prepare_snake_zrb_app_name_backend,
    ],
    cwd=APP_DIR,
    env_files=[app_env_file],
    envs=[app_enable_otel_env],
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "activate-venv.sh"),
        os.path.join(CURRENT_DIR, "cmd", "app-start.sh"),
    ],
    checkers=[
        app_local_checker,
    ],
)

###############################################################################
# ⚙️ start-kebab-zrb-task-name-gateway
###############################################################################

start_snake_zrb_app_name_gateway = CmdTask(
    icon="🚪",
    name="start-kebab-zrb-app-name-gateway",
    inputs=[
        local_input,
        enable_monitoring_input,
        run_mode_input,
        host_input,
        https_input,
    ],
    should_execute=should_start_local_microservices,
    upstreams=[
        start_snake_zrb_app_name_support_container,
        build_snake_zrb_app_name_frontend,
        prepare_snake_zrb_app_name_backend,
    ],
    cwd=APP_DIR,
    env_files=[
        app_env_file,
    ],
    envs=[
        Env(name="APP_DB_AUTO_MIGRATE", default="false", os_name=""),
        Env(name="APP_ENABLE_EVENT_HANDLER", default="false", os_name=""),
        Env(name="APP_ENABLE_RPC_SERVER", default="false", os_name=""),
        app_enable_otel_env,
    ],
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "activate-venv.sh"),
        os.path.join(CURRENT_DIR, "cmd", "app-start.sh"),
    ],
    checkers=[
        app_local_checker,
    ],
)

###############################################################################
# ⚙️ start-kebab-zrb-task-name
###############################################################################

start_snake_zrb_app_name = Task(
    icon="🚤",
    name="start-kebab-zrb-app-name",
    description="Start human readable zrb app name",
    group=project_group,
    upstreams=[
        start_monolith_snake_zrb_app_name,
        start_snake_zrb_app_name_gateway,
        *get_start_microservices(
            upstreams=[
                start_snake_zrb_app_name_support_container,
                build_snake_zrb_app_name_frontend,
                prepare_snake_zrb_app_name_backend,
            ]
        ),
    ],
    run=lambda *args, **kwargs: kwargs.get("_task").print_out("🆗"),
)
runner.register(start_snake_zrb_app_name)
