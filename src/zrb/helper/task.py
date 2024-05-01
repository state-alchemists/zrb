from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.task.task import Task

logger.debug(colored("Loading zrb.helper.task", attrs=["dark"]))


@typechecked
def show_lines(task: Task, *lines: str):
    separator = "\n    "
    task.print_out("\n" + separator + separator.join(lines) + "\n", trim_message=False)
