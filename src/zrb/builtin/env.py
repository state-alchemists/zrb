from zrb.builtin.group import env_group
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any, List
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.task import Task

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name="get", group=env_group, description="Get environment values", runner=runner
)
async def get(*args: Any, **kwargs: Any):
    task: Task = kwargs["_task"]
    env_map = task.get_env_map()
    names = list(env_map.keys())
    names.sort()
    colored_equal = colored("=", color="grey", attrs=["dark"])
    env_lines: List[str] = []
    for name in names:
        value = env_map[name]
        colored_name = colored(name, color="green", attrs=["bold"])
        colored_value = colored(value, attrs=["bold"])
        env_lines.append(f"{colored_name}{colored_equal}{colored_value}")
    line_separator = "\n    "
    task.print_out(line_separator + line_separator.join(env_lines))
    return env_map
