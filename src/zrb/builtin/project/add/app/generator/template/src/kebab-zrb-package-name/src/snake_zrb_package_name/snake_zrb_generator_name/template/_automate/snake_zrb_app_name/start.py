import os

from zrb import CmdTask, Env, EnvFile, HTTPChecker, runner

from .._project import start_project
from ._constant import APP_DIR, APP_TEMPLATE_ENV_FILE_NAME
from ._group import snake_zrb_app_name_group
from ._input import host_input, https_input, local_input

_CURRENT_DIR = os.path.dirname(__file__)


start_snake_zrb_app_name = CmdTask(
    icon="🚤",
    name="start",
    description="Start human readable zrb app name",
    group=snake_zrb_app_name_group,
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
        os.path.join(_CURRENT_DIR, "activate-venv.sh"),
        os.path.join(_CURRENT_DIR, "start.sh"),
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

start_snake_zrb_app_name >> start_project

runner.register(start_snake_zrb_app_name)
