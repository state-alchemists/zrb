from zrb.helper.task import show_lines as task_show_lines
from zrb.helper.typecheck import typechecked
from zrb.task.task import Task


@typechecked
def show_lines(task: Task, *lines: str):
    task.print_err("Deprecated: Use zrb.helper.task.show_lines instead")
    task_show_lines(task, *lines)
