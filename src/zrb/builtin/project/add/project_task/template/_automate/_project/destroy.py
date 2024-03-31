from zrb import Task, python_task, runner
from zrb.builtin import project_group
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any


@python_task(
    name="destroy",
    group=project_group,
    description="Destroy project deployment",
    runner=runner,
)
def destroy_project(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Project deployment destroyed", color="yellow"))
