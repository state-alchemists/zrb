import os

from zrb import CmdTask, runner

from ..._project import start_project
from .._checker import app_local_checker
from .._constant import APP_DIR, AUTOMATE_DIR, PREFER_MICROSERVICES
from .._env import app_enable_otel_env, app_env_file
from .._input import host_input, https_input, local_input
from ..backend import prepare_snake_zrb_app_name_backend
from ..container._input import enable_monitoring_input
from ..container.support import start_snake_zrb_app_name_support_container
from ..frontend import build_snake_zrb_app_name_frontend
from ._group import snake_zrb_app_name_monolith_group

_CURRENT_DIR = os.path.dirname(__file__)

start_snake_zrb_app_name_monolith = CmdTask(
    icon="🚤",
    name="start",
    inputs=[
        local_input,
        enable_monitoring_input,
        host_input,
        https_input,
    ],
    description="Start human readable zrb app name as a monolith",
    group=snake_zrb_app_name_monolith_group,
    should_execute="{{ input.local_snake_zrb_app_name}}",
    upstreams=[
        start_snake_zrb_app_name_support_container,
        build_snake_zrb_app_name_frontend,
        prepare_snake_zrb_app_name_backend,
    ],
    cwd=APP_DIR,
    env_files=[app_env_file],
    envs=[app_enable_otel_env],
    cmd_path=[
        os.path.join(AUTOMATE_DIR, "activate-venv.sh"),
        os.path.join(_CURRENT_DIR, "start.sh"),
    ],
    checkers=[
        app_local_checker,
    ],
)

if not PREFER_MICROSERVICES:
    start_snake_zrb_app_name_monolith >> start_project

runner.register(start_snake_zrb_app_name_monolith)
