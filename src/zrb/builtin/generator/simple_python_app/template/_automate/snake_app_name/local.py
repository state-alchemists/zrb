from zrb import (
    CmdTask, Env, EnvFile, HTTPChecker, runner
)
from zrb.builtin._group import project_group
from .common import (
    local_snake_app_name_input, snake_app_name_host_input,
    snake_app_name_https_input
)
import os

current_dir = os.path.dirname(__file__)
resource_dir = os.path.abspath(os.path.join(
    current_dir, '..', '..', 'src', 'kebab-app-name'
))
template_env_file = os.path.join(resource_dir, 'src', 'template.env')

app_env_file = EnvFile(env_file=template_env_file, prefix='ENV_PREFIX')

start_snake_app_name = CmdTask(
    name='start-kebab-app-name',
    description='Start human readable app name',
    group=project_group,
    inputs=[
        local_snake_app_name_input,
        snake_app_name_host_input,
        snake_app_name_https_input
    ],
    skip_execution='{{not input.local_snake_app_name}}',
    cwd=os.path.join(resource_dir, 'src'),
    env_files=[app_env_file],
    envs=[
        Env(
            name='APP_PORT',
            os_name='ENV_PREFIX_APP_PORT',
            default='httpPort'
        )
    ],
    cmd_path=os.path.join(current_dir, 'cmd', 'start.sh'),
    checkers=[
        HTTPChecker(
            host='{{input.snake_app_name_host}}',
            port='{{env.APP_PORT}}',
            is_https='{{input.snake_app_name_https}}'
        )
    ]
)
runner.register(start_snake_app_name)
