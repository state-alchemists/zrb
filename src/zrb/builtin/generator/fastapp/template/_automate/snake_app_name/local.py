from typing import Any
from zrb import CmdTask, DockerComposeTask, Task, Env, EnvFile, runner
from zrb.builtin._group import project_group
from ._common import (
    CURRENT_DIR, APP_DIR, APP_TEMPLATE_ENV_FILE_NAME, RESOURCE_DIR,
    skip_local_microservices_execution,
    rabbitmq_checker, rabbitmq_management_checker,
    redpanda_console_checker, kafka_outside_checker,
    kafka_plaintext_checker, pandaproxy_outside_checker,
    pandaproxy_plaintext_checker, app_local_checker,
    local_input, run_mode_input, host_input, https_input,
    local_app_port_env, local_app_broker_type_env
)
from .image import image_input
from .frontend import build_snake_app_name_frontend
from .container import remove_snake_app_name_container
from .local_microservices import get_start_microservices
import os

###############################################################################
# Functions
###############################################################################


def setup_support_compose_profile(*args: Any, **kwargs: Any) -> str:
    task: Task = kwargs.get('_task')
    env_map = task.get_env_map()
    compose_profiles = ','.join([
        env_map.get('APP_PBROKER_TYPE', 'rabbitmq'),
    ])
    return f'export COMPOSE_PROFILES={compose_profiles}'


def skip_support_container_execution(*args: Any, **kwargs: Any) -> bool:
    if not kwargs.get('local_snake_app_name', True):
        return True
    task: Task = kwargs.get('_task')
    env_map = task.get_env_map()
    broker_type = env_map.get('APP_BROKER_TYPE', 'rabbitmq')
    return broker_type not in ['rabbitmq', 'kafka']


def skip_local_monolith_execution(*args: Any, **kwargs: Any) -> bool:
    if not kwargs.get('local_snake_app_name', True):
        return True
    return kwargs.get('snake_app_name_run_mode', 'monolith') != 'monolith'


###############################################################################
# Env file Definitions
###############################################################################

app_env_file = EnvFile(
    env_file=APP_TEMPLATE_ENV_FILE_NAME, prefix='ENV_PREFIX'
)

###############################################################################
# Task Definitions
###############################################################################

init_snake_app_name_support_container = DockerComposeTask(
    icon='🔥',
    name='init-kebab-app-name-support-container',
    inputs=[
        local_input,
        host_input,
        image_input,
    ],
    skip_execution=skip_support_container_execution,
    upstreams=[
        remove_snake_app_name_container
    ],
    cwd=RESOURCE_DIR,
    setup_cmd=setup_support_compose_profile,
    compose_cmd='up',
    compose_flags=['-d'],
    compose_env_prefix='CONTAINER_ENV_PREFIX',
    envs=[
        local_app_broker_type_env,
        local_app_port_env,
    ],
)

start_snake_app_name_support_container = DockerComposeTask(
    icon='🐳',
    name='start-kebab-app-name-support-container',
    description='Start human readable app name container',
    inputs=[
        local_input,
        host_input,
        https_input,
        image_input,
    ],
    skip_execution=skip_support_container_execution,
    upstreams=[init_snake_app_name_support_container],
    cwd=RESOURCE_DIR,
    setup_cmd=setup_support_compose_profile,
    compose_cmd='logs',
    compose_flags=['-f'],
    compose_env_prefix='CONTAINER_ENV_PREFIX',
    envs=[
        local_app_broker_type_env,
        local_app_port_env,
    ],
    checkers=[
        rabbitmq_checker,
        rabbitmq_management_checker,
        kafka_outside_checker,
        kafka_plaintext_checker,
        redpanda_console_checker,
        pandaproxy_outside_checker,
        pandaproxy_plaintext_checker,
    ]
)

prepare_snake_app_name_backend = CmdTask(
    icon='🚤',
    name='prepare-kebab-app-name-backend',
    description='Prepare backend for human readable app name',
    group=project_group,
    cwd=APP_DIR,
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'prepare-backend.sh'),
)
runner.register(prepare_snake_app_name_backend)

start_monolith_snake_app_name = CmdTask(
    icon='🚤',
    name='start-monolith-kebab-app-name',
    inputs=[
        local_input,
        run_mode_input,
        host_input,
        https_input
    ],
    skip_execution=skip_local_monolith_execution,
    upstreams=[
        start_snake_app_name_support_container,
        build_snake_app_name_frontend,
        prepare_snake_app_name_backend,
    ],
    cwd=APP_DIR,
    env_files=[app_env_file],
    envs=[
        local_app_broker_type_env,
        local_app_port_env,
    ],
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'start.sh'),
    checkers=[
        app_local_checker,
    ]
)

start_snake_app_name_gateway = CmdTask(
    icon='🚪',
    name='start-kebab-app-name-gateway',
    inputs=[
        local_input,
        run_mode_input,
        host_input,
        https_input
    ],
    skip_execution=skip_local_microservices_execution,
    upstreams=[
        start_snake_app_name_support_container,
        build_snake_app_name_frontend,
        prepare_snake_app_name_backend,
    ],
    cwd=APP_DIR,
    env_files=[app_env_file],
    envs=[
        local_app_broker_type_env,
        local_app_port_env,
        Env(name='APP_DB_AUTO_MIGRATE', default='false', os_name=''),
        Env(name='APP_ENABLE_EVENT_HANDLER', default='false', os_name=''),
        Env(name='APP_ENABLE_RPC_SERVER', default='false', os_name=''),
    ],
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'start.sh'),
    checkers=[
        app_local_checker,
    ]
)

start_microservices = get_start_microservices(
    upstreams=[
        start_snake_app_name_support_container,
        build_snake_app_name_frontend,
        prepare_snake_app_name_backend,
    ]
)

start_snake_app_name = Task(
    icon='🚤',
    name='start-kebab-app-name',
    description='Start human readable app name',
    group=project_group,
    upstreams=[
        start_monolith_snake_app_name,
        start_snake_app_name_gateway,
    ] + start_microservices,
    run=lambda *args, **kwargs: kwargs.get('_task').print_out('🆗')
)
runner.register(start_snake_app_name)
