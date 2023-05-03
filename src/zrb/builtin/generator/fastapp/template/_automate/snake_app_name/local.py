from zrb import CmdTask, DockerComposeTask, Task, Env, EnvFile, runner
from zrb.builtin._group import project_group
from ._common import (
    CURRENT_DIR, APP_DIR, RESOURCE_DIR, APP_TEMPLATE_ENV_FILE_NAME,
    SKIP_SUPPORT_CONTAINER_EXECUTION, SKIP_LOCAL_MONOLITH_EXECUTION,
    SKIP_LOCAL_MICROSERVICES_EXECUTION,
    rabbitmq_checker, rabbitmq_management_checker,
    redpanda_console_checker, kafka_outside_checker,
    kafka_plaintext_checker, pandaproxy_outside_checker,
    pandaproxy_plaintext_checker, app_local_checker,
    local_input, mode_input, host_input, https_input, image_input,
    local_app_port_env, local_app_broker_type_env,
)
from .image import build_snake_app_name_image
from .frontend import build_snake_app_name_frontend
from .container import remove_snake_app_name_container
from .local_microservices import get_start_microservices
import os

support_compose_env_prefix = 'CONTAINER_ENV_PREFIX'
start_broker_compose_profile = '{{env.get("APP_BROKER_TYPE", "rabbitmq")}}'

###############################################################################
# Task Definitions
###############################################################################

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
    skip_execution=SKIP_SUPPORT_CONTAINER_EXECUTION,
    upstreams=[
        build_snake_app_name_image,
        remove_snake_app_name_container
    ],
    cwd=RESOURCE_DIR,
    setup_cmd=f'export COMPOSE_PROFILES={start_broker_compose_profile}',
    compose_cmd='up',
    compose_env_prefix=support_compose_env_prefix,
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
        mode_input,
        host_input,
        https_input
    ],
    skip_execution=SKIP_LOCAL_MONOLITH_EXECUTION,
    upstreams=[
        start_snake_app_name_support_container,
        build_snake_app_name_frontend,
        prepare_snake_app_name_backend,
    ],
    cwd=APP_DIR,
    env_files=[
        EnvFile(
            env_file=APP_TEMPLATE_ENV_FILE_NAME, prefix='ENV_PREFIX'
        ),
    ],
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
        mode_input,
        host_input,
        https_input
    ],
    skip_execution=SKIP_LOCAL_MICROSERVICES_EXECUTION,
    upstreams=[
        start_snake_app_name_support_container,
        build_snake_app_name_frontend,
        prepare_snake_app_name_backend,
    ],
    cwd=APP_DIR,
    env_files=[
       EnvFile(
            env_file=APP_TEMPLATE_ENV_FILE_NAME, prefix='ENV_PREFIX'
        ), 
    ],
    envs=[
        local_app_broker_type_env,
        local_app_port_env,
        Env(name='APP_ENABLE_MESSAGE_CONSUMER', default='false', os_name=''),
        Env(name='APP_ENABLE_RPC_SERVER', default='false', os_name=''),
    ],
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'start.sh'),
    checkers=[
        app_local_checker,
    ]
)
runner.register(start_snake_app_name_gateway)

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
    run=lambda *args, **kwargs: kwargs.get('_task').print_out('👌')
)
runner.register(start_snake_app_name)
