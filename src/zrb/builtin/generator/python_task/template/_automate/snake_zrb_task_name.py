from typing import Any, Mapping

from zrb import Task, python_task, runner
from zrb.builtin.group import project_group

###############################################################################
# ⚙️ kebab-zrb-task-name
###############################################################################


@python_task(
    name="kebab-zrb-task-name",
    description="human readable zrb task name",
    group=project_group,
    runner=runner,
)
async def snake_zrb_task_name(*args: Any, **kwargs: Any) -> Any:
    task: Task = kwargs.get("_task")
    env_map: Mapping[str, str] = task.get_env_map()
    input_map: Mapping[str, str] = task.get_input_map()
    task.print_out(f"Env map: {env_map}")
    task.print_out(f"Input map: {input_map}")
    return "ok"
