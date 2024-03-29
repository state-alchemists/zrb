from zrb.helper.typecheck import typechecked
from zrb.task.task import Task


@typechecked
def show_lines(task: Task, *lines: str):
    separator = "\n    "
    task.print_out("\n" + separator + separator.join(lines) + "\n", trim_message=False)
