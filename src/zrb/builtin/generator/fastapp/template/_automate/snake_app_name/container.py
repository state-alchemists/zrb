from typing import Mapping, Any
from zrb import DockerComposeTask, ServiceConfig, EnvFile, runner, Task
from zrb.helper.util import to_kebab_case
from zrb.builtin._group import project_group
from ._common import (
    APP_TEMPLATE_ENV_FILE_NAME, CURRENT_DIR, RESOURCE_DIR, MODULES,
    app_container_checker, rabbitmq_checker, rabbitmq_management_checker,
    redpanda_console_checker, kafka_outside_checker, kafka_plaintext_checker,
    pandaproxy_outside_checker, pandaproxy_plaintext_checker, local_input,
    run_mode_input, enable_monitoring_input, host_input, https_input
)
from .image import build_snake_app_name_image, image_input, image_env
import os

###############################################################################
# Functions
###############################################################################


def setup_runtime_compose_profile(*args: Any, **kwargs: Any) -> str:
    task: Task = kwargs.get('_task')
    env_map = task.get_env_map()
    compose_profiles = [
        env_map.get('APP_PBROKER_TYPE', 'rabbitmq'),
        kwargs.get('snake_app_name_run_mode', 'monolith'),
    ]
    if kwargs.get('enable_snake_app_name_monitoring', False):
        compose_profiles.append('monitoring')
    compose_profile_str = ','.join(compose_profiles)
    return f'export COMPOSE_PROFILES={compose_profile_str}'


def setup_all_compose_profile(*args: Any, **kwargs: Any) -> str:
    compose_profiles = [
        'monitoring',
        'monolith',
        'microservices',
        'kafka',
        'rabbitmq'
    ]
    compose_profile_str = ','.join(compose_profiles)
    return f'export COMPOSE_PROFILES={compose_profile_str}'


def skip_execution(*args: Any, **kwargs: Any) -> bool:
    return not kwargs.get('local_snake_app_name', True)


###############################################################################
# Env File Definitions
###############################################################################

compose_env_file = EnvFile(
    env_file=os.path.join(CURRENT_DIR, 'config', 'docker-compose.env'),
    prefix='CONTAINER_ENV_PREFIX'
)

###############################################################################
# Compose Service Config Definitions
###############################################################################

service_config_env_file = EnvFile(
    env_file=APP_TEMPLATE_ENV_FILE_NAME, prefix='CONTAINER_ENV_PREFIX'
)
service_configs: Mapping[str, ServiceConfig] = {
    'kebab-app-name': ServiceConfig(env_files=[service_config_env_file])
}
modules = ['gateway'] + MODULES
for module in modules:
    service_name = 'kebab-app-name-' + to_kebab_case(module)
    service_configs[service_name] = ServiceConfig(
        env_files=[service_config_env_file]
    )

###############################################################################
# Task Definitions
###############################################################################

remove_snake_app_name_container = DockerComposeTask(
    icon='💨',
    name='remove-kebab-app-name-container',
    description='Rumove human readable app name container',
    group=project_group,
    cwd=RESOURCE_DIR,
    setup_cmd=setup_all_compose_profile,
    compose_cmd='down',
    compose_env_prefix='CONTAINER_ENV_PREFIX',
    compose_service_configs=service_configs,
    envs=[image_env],
    env_files=[compose_env_file]
)
runner.register(remove_snake_app_name_container)

init_snake_app_name_container = DockerComposeTask(
    icon='🔥',
    name='init-kebab-app-name-container',
    group=project_group,
    inputs=[
        local_input,
        enable_monitoring_input,
        run_mode_input,
        host_input,
        image_input,
    ],
    skip_execution=skip_execution,
    upstreams=[
        build_snake_app_name_image,
        remove_snake_app_name_container
    ],
    cwd=RESOURCE_DIR,
    setup_cmd=setup_runtime_compose_profile,
    compose_cmd='up',
    compose_flags=['-d'],
    compose_env_prefix='CONTAINER_ENV_PREFIX',
    compose_service_configs=service_configs,
    envs=[image_env],
    env_files=[compose_env_file],
)

start_snake_app_name_container = DockerComposeTask(
    icon='🐳',
    name='start-kebab-app-name-container',
    description='Start human readable app name container',
    group=project_group,
    inputs=[
        local_input,
        run_mode_input,
        host_input,
        https_input,
        image_input,
    ],
    skip_execution=skip_execution,
    upstreams=[init_snake_app_name_container],
    cwd=RESOURCE_DIR,
    setup_cmd=setup_runtime_compose_profile,
    compose_cmd='logs',
    compose_flags=['-f'],
    compose_env_prefix='CONTAINER_ENV_PREFIX',
    compose_service_configs=service_configs,
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
    ]
)
runner.register(start_snake_app_name_container)

stop_snake_app_name_container = DockerComposeTask(
    icon='⛔',
    name='stop-kebab-app-name-container',
    description='Stop human readable app name container',
    group=project_group,
    cwd=RESOURCE_DIR,
    setup_cmd=setup_all_compose_profile,
    compose_cmd='stop',
    compose_env_prefix='CONTAINER_ENV_PREFIX',
    compose_service_configs=service_configs,
    envs=[image_env],
    env_files=[compose_env_file]
)
runner.register(stop_snake_app_name_container)
