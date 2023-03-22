from zrb import DockerComposeTask, Env, HTTPChecker, runner
from zrb.builtin._group import project_group
from .common import (
    RESOURCE_DIR,
    local_input, host_input, https_input, image_input
)
from .image import build_snake_app_name_image
from .compose.compose_env import compose_env_prefix, compose_envs
from .compose.compose_checker import (
    rabbitmq_checker, rabbitmq_management_checker,
    redpanda_console_checker, kafka_outside_checker,
    kafka_plaintext_checker, pandaproxy_outside_checker,
    pandaproxy_plaintext_checker
)


remove_snake_app_name_container = DockerComposeTask(
    icon='💨',
    name='remove-kebab-app-name-container',
    description='Rumove human readable app name container',
    group=project_group,
    cwd=RESOURCE_DIR,
    compose_cmd='down',
    compose_env_prefix=compose_env_prefix,
    envs=compose_envs,
)
runner.register(remove_snake_app_name_container)

start_snake_app_name_container = DockerComposeTask(
    icon='🐳',
    name='start-kebab-app-name-container',
    description='Start human readable app name container',
    group=project_group,
    inputs=[
        local_input,
        host_input,
        https_input,
        image_input,
    ],
    skip_execution='{{not input.local_snake_app_name}}',
    upstreams=[
        build_snake_app_name_image,
        remove_snake_app_name_container
    ],
    cwd=RESOURCE_DIR,
    compose_cmd='up',
    compose_env_prefix=compose_env_prefix,
    envs=compose_envs + [
        Env(
            name='COMPOSE_PROFILES',
            os_name='',
            default=' '.join([
                '{{',
                '",".join([',
                '  env.get("APP_BROKER_TYPE", "rabbitmq"),',
                '  "monolith"',
                '])',
                '}}'
            ])
        )
    ],
    checkers=[
        HTTPChecker(
            name='check-kebab-app-name-monolith',
            host='{{input.snake_app_name_host}}',
            url='/readiness',
            port='{{env.get("HOST_PORT", "httpPort")}}',
            is_https='{{input.snake_app_name_https}}'
        ),
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
    compose_cmd='stop',
    compose_env_prefix=compose_env_prefix,
    envs=compose_envs,
)
runner.register(stop_snake_app_name_container)
