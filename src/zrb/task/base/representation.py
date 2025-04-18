from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.task.base_task import BaseTask


def get_task_repr(task: "BaseTask") -> str:
    """
    Generates the string representation for a BaseTask instance.
    """
    # Access the _name attribute directly, assuming it exists from __init__
    name = getattr(task, "_name", "UnknownTask")
    return f"<{task.__class__.__name__} name={name}>"
