from my_app_name._zrb.config import APP_DIR
from my_app_name._zrb.group import app_group

from zrb.task.cmd_task import CmdTask

format_my_app_name_code = app_group.add_task(
    CmdTask(
        name="format-my-app-name-code",
        description="✨ Format Python code",
        cmd=[
            "isort . --profile black --force-grid-wrap 0",
            "black .",
        ],
        cwd=APP_DIR,
    ),
    alias="format",
)
