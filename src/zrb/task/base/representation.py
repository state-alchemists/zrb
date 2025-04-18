from zrb.task.base_task import BaseTask


def get_task_repr(task: BaseTask) -> str:
    """
    Generates the string representation for a BaseTask instance.
    """
    # Access the _name attribute directly as task is BaseTask
    name = task._name
    return f"<{task.__class__.__name__} name={name}>"
