from zrb import CmdTask, runner
from ._group import project_container_group

remove_project_container = CmdTask(
    name="remove",
    group=project_container_group,
    description="Remove project containers",
    cmd="echo Project containers removed."
)
runner.register(remove_project_container)
