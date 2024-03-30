from zrb import python_task, Task, runner
from zrb.helper.typing import Any
from zrb.helper.accessories.color import colored
from ._group import project_container_group


@python_task(
    name="stop",
    group=project_container_group,
    description="Stop project containers",
    runner=runner
)
def stop_project_containers(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Project containers stoped", color="yellow"))
