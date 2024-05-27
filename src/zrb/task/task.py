from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.task.base_task.base_task import BaseTask

logger.debug(colored("Loading zrb.task.task", attrs=["dark"]))


@typechecked
class Task(BaseTask):
    """
    The task is the smallest Zrb automation unit.

    You can configure a Task by using several interfaces:
    - `inputs`: interfaces to read user input at the beginning of the execution.
    - `envs`: interfaces to read and use OS Environment Variables.
    - `env_files`: interfaces to read and use Environment Files.

    Moreover, you can define Task dependencies by specifying it's `upstreams` or by using shift-right operator.

    Finally, you can put related Tasks under the same `group`.
    """

    pass
