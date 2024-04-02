import os

from zrb.task_input.str_input import StrInput

SYSTEM_USER = os.getenv("USER", "incognito")

project_dir_input = StrInput(
    name="project-dir",
    shortcut="d",
    description="Project directory",
    prompt="Project directory",
    default=".",
)
