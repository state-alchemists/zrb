from zrb import Task, python_task, runner
from zrb.builtin import project_group
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any


@python_task(
    name="build",
    group=project_group,
    description="Build project artifacts",
    runner=runner,
)
def build_project(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Project artifact built", color="yellow"))
