from zrb import CmdTask, runner
from ._group import project_group

publish_project = CmdTask(
    name="publish",
    group=project_group,
    description="Publish project artifacts",
    cmd="echo Project artifact published."
)
runner.register(publish_project)
