from zrb import CmdTask, runner
from ._group import project_container_group

stop_project_container = CmdTask(
    name="stop",
    group=project_container_group,
    description="Stop project containers",
    cmd="echo Project containers stopped."
)
runner.register(stop_project_container)
