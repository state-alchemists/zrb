import os

from zrb import CmdTask, Env, EnvFile, runner
from zrb.builtin.group import project_group

from ._checker import snake_zrb_app_name_checker
from ._common import (
    APP_DIR,
    APP_TEMPLATE_ENV_FILE_NAME,
    CURRENT_DIR,
    host_input,
    local_input,
)

###############################################################################
# 🌳 Env File Definitions
###############################################################################

app_env_file = EnvFile(path=APP_TEMPLATE_ENV_FILE_NAME, prefix="ZRB_ENV_PREFIX")

###############################################################################
# ⚙️ start_kebab-zrb-task-name
###############################################################################

start_snake_zrb_app_name = CmdTask(
    icon="🚤",
    name="start-kebab-zrb-app-name",
    description="Start human readable zrb app name",
    group=project_group,
    inputs=[
        local_input,
        host_input,
    ],
    should_execute="{{input.local_snake_zrb_app_name}}",
    cwd=APP_DIR,
    env_files=[app_env_file],
    envs=[
        Env(name="APP_PORT", os_name="ZRB_ENV_PREFIX_APP_PORT", default="zrbAppPort")
    ],
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "app-activate-venv.sh"),
        os.path.join(CURRENT_DIR, "cmd", "app-start.sh"),
    ],
    checkers=[
        snake_zrb_app_name_checker,
    ],
)
runner.register(start_snake_zrb_app_name)
