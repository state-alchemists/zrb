from zrb import CmdTask, runner
from ._group import project_image_group

push_project_image = CmdTask(
    name="push",
    group=project_image_group,
    description="Push project image",
    cmd="echo Project images pushed."
)
runner.register(push_project_image)
