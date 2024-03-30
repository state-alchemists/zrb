from zrb import python_task, Task, runner
from zrb.builtin import project_group
from zrb.helper.typing import Any
from zrb.helper.accessories.color import colored


@python_task(
    name="publish",
    group=project_group,
    description="Publish project artifacts",
    runner=runner
)
def publish_project(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Project artifact published", color="yellow"))
