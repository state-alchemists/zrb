from zrb import CmdTask, DockerComposeTask, Env, HTTPChecker, runner
from zrb.builtin._group import project_group
from .common import (
    CURRENT_DIR, APP_DIR, RESOURCE_DIR,
    local_input, host_input, https_input, image_input
)
from .image import build_snake_app_name_image
from .app.app_env import app_env_file, app_envs
from .container import remove_snake_app_name_container
from .compose.compose_env import compose_env_prefix, compose_envs
from .compose.compose_checker import (
    rabbitmq_checker, rabbitmq_management_checker,
    redpanda_console_checker, kafka_outside_checker,
    kafka_plaintext_checker, pandaproxy_outside_checker,
    pandaproxy_plaintext_checker
)
import os

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
    skip_execution=' '.join([
        '{{',
        'not input.local_snake_app_name',
        'or env.get("APP_BROKER_TYPE") == "mock"',
        '}}',
    ]),
    upstreams=[
        build_snake_app_name_image,
        remove_snake_app_name_container
    ],
    cwd=RESOURCE_DIR,
    compose_cmd='up',
    compose_env_prefix=compose_env_prefix,
    envs=compose_envs + app_envs + [
        Env(
            name='COMPOSE_PROFILES',
            os_name='',
            default=' '.join([
                '{{',
                '",".join([',
                '  env.get("APP_BROKER_TYPE", "rabbitmq"),',
                '])',
                '}}'
            ])
        )
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

start_snake_app_name = CmdTask(
    icon='🚤',
    name='start-kebab-app-name',
    description='Start human readable app name',
    group=project_group,
    inputs=[
        local_input,
        host_input,
        https_input
    ],
    skip_execution='{{not input.local_snake_app_name}}',
    upstreams=[start_snake_app_name_support_container],
    cwd=APP_DIR,
    env_files=[app_env_file],
    envs=app_envs,
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'start.sh'),
    checkers=[
        HTTPChecker(
            name='check-kebab-app-name',
            host='{{input.snake_app_name_host}}',
            url='/readiness',
            port='{{env.APP_PORT}}',
            is_https='{{input.snake_app_name_https}}'
        )
    ]
)
runner.register(start_snake_app_name)
