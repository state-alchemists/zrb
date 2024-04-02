from zrb import Task, python_task, runner
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any

from ._group import project_container_group


@python_task(
    name="remove",
    group=project_container_group,
    description="Remove project containers",
    runner=runner,
)
def remove_project_containers(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Project containers removed", color="yellow"))
