from zrb.builtin.group import python_group
from zrb.task.cmd_task import CmdTask

format_python_code = python_group.add_task(
    CmdTask(
        name="format-code",
        description="✏️ Format Python code",
        cmd=["isort .", "black ."],
    ),
    alias="format",
)
