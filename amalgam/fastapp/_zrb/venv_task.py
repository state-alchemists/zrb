import os

from fastapp._zrb.config import ACTIVATE_VENV_SCRIPT, APP_DIR
from fastapp._zrb.group import app_group

from zrb import CmdTask

create_venv = CmdTask(
    name="create-fastapp-venv",
    cwd=APP_DIR,
    cmd="python -m venv .venv",
    execute_condition=lambda _: not os.path.isdir(os.path.join(APP_DIR, ".venv")),
)

prepare_venv = CmdTask(
    name="prepare-fastapp-venv",
    cmd=[ACTIVATE_VENV_SCRIPT, "pip install -r requirements.txt"],
    cwd=APP_DIR,
)
create_venv >> prepare_venv

app_group.add_task(create_venv, alias="prepare")
