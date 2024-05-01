from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.task.base_task.base_task import BaseTask

logger.debug(colored("Loading zrb.task.task", attrs=["dark"]))


@typechecked
class Task(BaseTask):
    """
    Alias for BaseTask.
    """

    pass
