from zrb import python_task, Task, runner
from zrb.helper.typing import Any
from zrb.helper.accessories.color import colored
from ._group import project_image_group


@python_task(
    name="build",
    group=project_image_group,
    description="Build project images",
    runner=runner
)
def build_project_images(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Project images built", color="yellow"))
