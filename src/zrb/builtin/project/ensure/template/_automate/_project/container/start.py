from zrb import CmdTask, runner
from ._group import project_container_group

start_project_container = CmdTask(
    name="start",
    group=project_container_group,
    description="Start project containers",
    cmd="echo Project containers started."
)
runner.register(start_project_container)
