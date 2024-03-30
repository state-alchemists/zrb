from zrb import CmdTask, runner
from ._group import project_image_group

build_project_image = CmdTask(
    name="build",
    group=project_image_group,
    description="Build project image",
    cmd="echo Project images built."
)
runner.register(build_project_image)
