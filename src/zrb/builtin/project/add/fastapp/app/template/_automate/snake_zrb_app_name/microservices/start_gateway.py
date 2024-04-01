import os

from zrb import CmdTask, Env

from .._checker import app_local_checker
from .._constant import APP_DIR, AUTOMATE_DIR
from .._env import app_enable_otel_env, app_env_file
from .._input import host_input, https_input, local_input
from ..backend import prepare_snake_zrb_app_name_backend
from ..container._input import enable_monitoring_input
from ..container.support import start_snake_zrb_app_name_support_container
from ..frontend import build_snake_zrb_app_name_frontend

_CURRENT_DIR = os.path.dirname(__file__)

start_snake_zrb_app_name_gateway = CmdTask(
    icon="🚪",
    name="start-kebab-zrb-app-name-gateway",
    inputs=[
        local_input,
        enable_monitoring_input,
        host_input,
        https_input,
    ],
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
        Env(name="APP_DB_AUTO_MIGRATE", default="false", os_name=""),
        Env(name="APP_ENABLE_EVENT_HANDLER", default="false", os_name=""),
        Env(name="APP_ENABLE_RPC_SERVER", default="false", os_name=""),
        app_enable_otel_env,
    ],
    cmd_path=[
        os.path.join(AUTOMATE_DIR, "activate-venv.sh"),
        os.path.join(_CURRENT_DIR, "start.sh"),
    ],
    checkers=[
        app_local_checker,
    ],
)
