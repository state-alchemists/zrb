from zrb import Task, python_task, runner
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any

from ._group import project_image_group


@python_task(
    name="push",
    group=project_image_group,
    description="Push project images",
    runner=runner,
)
def push_project_images(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Project images pushed", color="yellow"))
