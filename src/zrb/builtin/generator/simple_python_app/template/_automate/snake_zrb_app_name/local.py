import os

from zrb import CmdTask, Env, EnvFile, HTTPChecker, runner
from zrb.builtin.group import project_group

from ._common import (
    APP_DIR,
    APP_TEMPLATE_ENV_FILE_NAME,
    CURRENT_DIR,
    host_input,
    https_input,
    local_input,
)

###############################################################################
# ⚙️ kebab-zrb-task-name
###############################################################################

start_snake_zrb_app_name = CmdTask(
    icon="🚤",
    name="start-kebab-zrb-app-name",
    description="Start human readable zrb app name",
    group=project_group,
    inputs=[local_input, host_input, https_input],
    should_execute="{{ input.local_snake_zrb_app_name}}",
    cwd=APP_DIR,
    env_files=[EnvFile(path=APP_TEMPLATE_ENV_FILE_NAME, prefix="ZRB_ENV_PREFIX")],
    envs=[
        Env(
            name="APP_PORT", os_name="ZRB_ENV_PREFIX_APP_PORT", default="zrbAppHttpPort"
        )
    ],
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "app-activate-venv.sh"),
        os.path.join(CURRENT_DIR, "cmd", "app-start.sh"),
    ],
    checkers=[
        HTTPChecker(
            name="check-kebab-zrb-app-name",
            host="{{input.snake_zrb_app_name_host}}",
            port="{{env.APP_PORT}}",
            is_https="{{input.snake_zrb_app_name_https}}",
        )
    ],
)
runner.register(start_snake_zrb_app_name)
