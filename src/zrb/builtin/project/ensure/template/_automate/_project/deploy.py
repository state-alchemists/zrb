from zrb import CmdTask, runner
from ._group import project_group

deploy_project = CmdTask(
    name="deploy",
    group=project_group,
    description="Deploy project",
    cmd="echo Project deployed."
)
runner.register(deploy_project)
