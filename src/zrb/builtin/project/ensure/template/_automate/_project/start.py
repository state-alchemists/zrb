from zrb import CmdTask, runner
from ._group import project_group

start_project = CmdTask(
    name="start",
    group=project_group,
    description="Start project",
    cmd="echo Project started."
)
runner.register(start_project)
