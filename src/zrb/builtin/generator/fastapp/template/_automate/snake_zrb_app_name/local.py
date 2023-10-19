from typing import Any, List
from zrb import CmdTask, DockerComposeTask, Task, Env, EnvFile, runner
from zrb.builtin.group import project_group
from ._common import (
    CURRENT_DIR, APP_DIR, APP_TEMPLATE_ENV_FILE_NAME, RESOURCE_DIR,
    should_start_local_microservices, rabbitmq_checker,
    rabbitmq_management_checker, redpanda_console_checker,
    kafka_outside_checker, kafka_plaintext_checker, pandaproxy_outside_checker,
    pandaproxy_plaintext_checker, app_local_checker, local_input, https_input,
    run_mode_input, enable_monitoring_input, host_input, app_enable_otel_env
)
from .image import image_input
from .frontend import build_snake_zrb_app_name_frontend
from .container import remove_snake_zrb_app_name_container, compose_env_file
from .local_microservices import get_start_microservices
import os

###############################################################################
# Functions
###############################################################################


def setup_support_compose_profile(*args: Any, **kwargs: Any) -> str:
    task: Task = kwargs.get('_task')
    env_map = task.get_env_map()
    compose_profiles: List[str] = []
    broker_type = env_map.get('APP_BROKER_TYPE', 'rabbitmq')
    if broker_type in ['rabbitmq', 'kafka']:
        compose_profiles.append(broker_type)
    if kwargs.get('enable_snake_zrb_app_name_monitoring', False):
        compose_profiles.append('monitoring')
    compose_profile_str = ','.join(compose_profiles)
    return f'export COMPOSE_PROFILES={compose_profile_str}'


def should_start_support_container(*args: Any, **kwargs: Any) -> bool:
    return kwargs.get('local_snake_zrb_app_name', True)


def should_start_local_monolith(*args: Any, **kwargs: Any) -> bool:
    if not kwargs.get('local_snake_zrb_app_name', True):
        return False
    return kwargs.get('snake_zrb_app_name_run_mode', 'monolith') == 'monolith'


###############################################################################
# Env file Definitions
###############################################################################

app_env_file = EnvFile(
    env_file=APP_TEMPLATE_ENV_FILE_NAME, prefix='ZRB_ENV_PREFIX'
)

###############################################################################
# Task Definitions
###############################################################################

init_snake_zrb_app_name_support_container = DockerComposeTask(
    icon='🔥',
    name='init-kebab-zrb-app-name-support-container',
    inputs=[
        local_input,
        host_input,
        image_input,
    ],
    should_execute=should_start_support_container,
    upstreams=[
        remove_snake_zrb_app_name_container
    ],
    cwd=RESOURCE_DIR,
    setup_cmd=setup_support_compose_profile,
    compose_cmd='up',
    compose_flags=['-d'],
    compose_env_prefix='CONTAINER_ZRB_ENV_PREFIX',
    env_files=[compose_env_file]
)

start_snake_zrb_app_name_support_container = DockerComposeTask(
    icon='🐳',
    name='start-kebab-zrb-app-name-support-container',
    description='Start human readable zrb app name container',
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
    setup_cmd=setup_support_compose_profile,
    compose_cmd='logs',
    compose_flags=['-f'],
    compose_env_prefix='CONTAINER_ZRB_ENV_PREFIX',
    env_files=[compose_env_file],
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

prepare_snake_zrb_app_name_backend = CmdTask(
    icon='🚤',
    name='prepare-kebab-zrb-app-name-backend',
    description='Prepare backend for human readable zrb app name',
    group=project_group,
    cwd=APP_DIR,
    cmd_path=[
        os.path.join(CURRENT_DIR, 'cmd', 'activate-venv.sh'),
        os.path.join(CURRENT_DIR, 'cmd', 'app-prepare-backend.sh'),
    ]
)
runner.register(prepare_snake_zrb_app_name_backend)

start_monolith_snake_zrb_app_name = CmdTask(
    icon='🚤',
    name='start-monolith-kebab-zrb-app-name',
    inputs=[
        local_input,
        enable_monitoring_input,
        run_mode_input,
        host_input,
        https_input
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
        os.path.join(CURRENT_DIR, 'cmd', 'activate-venv.sh'),
        os.path.join(CURRENT_DIR, 'cmd', 'app-start.sh'),
    ],
    checkers=[
        app_local_checker,
    ]
)

start_snake_zrb_app_name_gateway = CmdTask(
    icon='🚪',
    name='start-kebab-zrb-app-name-gateway',
    inputs=[
        local_input,
        enable_monitoring_input,
        run_mode_input,
        host_input,
        https_input
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
        Env(name='APP_DB_AUTO_MIGRATE', default='false', os_name=''),
        Env(name='APP_ENABLE_EVENT_HANDLER', default='false', os_name=''),
        Env(name='APP_ENABLE_RPC_SERVER', default='false', os_name=''),
        app_enable_otel_env,
    ],
    cmd_path=[
        os.path.join(CURRENT_DIR, 'cmd', 'activate-venv.sh'),
        os.path.join(CURRENT_DIR, 'cmd', 'app-start.sh'),
    ],
    checkers=[
        app_local_checker,
    ]
)

start_microservices = get_start_microservices(
    upstreams=[
        start_snake_zrb_app_name_support_container,
        build_snake_zrb_app_name_frontend,
        prepare_snake_zrb_app_name_backend,
    ]
)

start_snake_zrb_app_name = Task(
    icon='🚤',
    name='start-kebab-zrb-app-name',
    description='Start human readable zrb app name',
    group=project_group,
    upstreams=[
        start_monolith_snake_zrb_app_name,
        start_snake_zrb_app_name_gateway,
    ] + start_microservices,
    run=lambda *args, **kwargs: kwargs.get('_task').print_out('🆗')
)
runner.register(start_snake_zrb_app_name)
