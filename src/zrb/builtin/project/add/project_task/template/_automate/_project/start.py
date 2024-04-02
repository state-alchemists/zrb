from zrb import Task, python_task, runner
from zrb.builtin import project_group
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any


@python_task(
    name="start", group=project_group, description="Start project", runner=runner
)
def start_project(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Project started", color="yellow"))
