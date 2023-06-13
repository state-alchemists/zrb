from zrb import CmdTask, Env, EnvFile, HTTPChecker, runner
from zrb.builtin._group import project_group
from ._common import (
    CURRENT_DIR, APP_DIR, TEMPLATE_ENV_FILE_NAME,
    local_input, host_input, https_input
)
import os

###############################################################################
# Env File Definitions
###############################################################################

app_env_file = EnvFile(env_file=TEMPLATE_ENV_FILE_NAME, prefix='ENV_PREFIX')

###############################################################################
# Task Definitions
###############################################################################

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
    cwd=APP_DIR,
    env_files=[app_env_file],
    envs=[
        Env(
            name='APP_PORT',
            os_name='ENV_PREFIX_APP_PORT',
            default='httpPort'
        )
    ],
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'start.sh'),
    checkers=[
        HTTPChecker(
            name='check-kebab-app-name',
            host='{{input.snake_app_name_host}}',
            port='{{env.APP_PORT}}',
            is_https='{{input.snake_app_name_https}}'
        )
    ]
)
runner.register(start_snake_app_name)
