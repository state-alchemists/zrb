import os

from zrb.task_input.str_input import StrInput

_PROJECT_DIR = os.getenv("ZRB_PROJECT_DIR", ".")

project_dir_input = StrInput(
    name="project-dir",
    shortcut="d",
    description="Project directory",
    prompt="Project directory",
    default=_PROJECT_DIR,
)
