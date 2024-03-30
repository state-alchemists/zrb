from zrb import python_task, Task, runner
from zrb.builtin import project_group
from zrb.helper.typing import Any
from zrb.helper.accessories.color import colored


@python_task(
    name="destroy",
    group=project_group,
    description="Destroy project deployment",
    runner=runner
)
def destroy_project(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Project deployment destroyed", color="yellow"))
