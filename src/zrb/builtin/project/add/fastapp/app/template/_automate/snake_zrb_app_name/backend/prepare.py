import os

from zrb import CmdTask, runner

from .._constant import APP_DIR, AUTOMATE_DIR
from ._group import snake_zrb_app_name_backend_group

_CURRENT_DIR = os.path.dirname(__file__)

prepare_snake_zrb_app_name_backend = CmdTask(
    icon="🚤",
    name="prepare",
    description="Prepare backend for human readable zrb app name",
    group=snake_zrb_app_name_backend_group,
    cwd=APP_DIR,
    cmd_path=[
        os.path.join(AUTOMATE_DIR, "activate-venv.sh"),
        os.path.join(_CURRENT_DIR, "prepare.sh"),
    ],
)
runner.register(prepare_snake_zrb_app_name_backend)
