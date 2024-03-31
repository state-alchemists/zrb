from zrb.helper.accessories.name import get_random_name
from zrb.task_input.str_input import StrInput

task_name_input = StrInput(
    name="task-name",
    shortcut="t",
    description="Task name",
    prompt="Task name",
    default=f"run-{get_random_name()}",
)
