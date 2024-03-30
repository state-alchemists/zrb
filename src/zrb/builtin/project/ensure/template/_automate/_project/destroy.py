from zrb import CmdTask, runner
from ._group import project_group

destroy_project = CmdTask(
    name="destroy",
    group=project_group,
    description="Destroy project deployment",
    cmd="echo Project deployment destroyed."
)
runner.register(destroy_project)
