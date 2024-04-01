import os

from zrb import CmdTask, runner

from .._constant import APP_FRONTEND_DIR
from .._env import app_env_file
from ._checker import check_frontend_path
from ._group import snake_zrb_app_name_frontend_group

_CURRENT_DIR = os.path.dirname(__file__)

build_snake_zrb_app_name_frontend_once = CmdTask(
    icon="🚤",
    name="build-once",
    description="Build frontend for human readable zrb app name",
    group=snake_zrb_app_name_frontend_group,
    cwd=APP_FRONTEND_DIR,
    cmd_path=os.path.join(_CURRENT_DIR, "build-once.sh"),
    checkers=[check_frontend_path],
    env_files=[app_env_file],
)
runner.register(build_snake_zrb_app_name_frontend_once)
