from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.task.base_task.base_task import BaseTask

logger.debug(colored("Loading zrb.task.task", attrs=["dark"]))


@typechecked
class Task(BaseTask):
    """
    Task is the smallest Zrb automation unit.

    You can configure a Task by using several interfaces:
    - `inputs`: interfaces to read user input at the beginning of the execution.
    - `envs`: interfaces to read and use OS Environment Variables.
    - `env_files`: interfaces to read and use Environment Files.

    Moreover, you can define Task dependencies by specifying it's `upstreams` or by using shift-right operator.

    Every Task has its own life-cycle state:
    - `Triggered`: The Task is triggered.
    - `Waiting`: The Task is waiting for all it's upstreams to be ready.
    - `Skipped`: The Task is not executed and will immediately enter the `Ready` state.
    - `Started`: The Task execution is started.
    - `Failed`: The Task execution is failed. It will enter the `Retry` state if the current attempt is less than the maximum attempt.
    - `Retry`: The task will be restarted.
    - `Ready`: The task is ready.

    There are several configurations related to Task's life cycle:
    - `retry`: How many retries should be attempted.
    - `retry_interval`: How long to wait before the next retry attempt.
    - `fallbacks`: What to do if the Task is failed and no retry attempt will be performed.
    - `checkers`: How to determine if a Task is `Ready`.
    - `checking_interval`: How long to wait before checking for Task's readiness.
    - `run`: What a Task should do.
    - `on_triggered`: What to do when a Task is `Triggered`.
    - `on_waiting`: What to do when a Task is `Waiting`.
    - `on_skipped`: What to do when a Task is `Skipped`.
    - `on_started`: What to do when a Task is `Started`.
    - `on_ready`: What to do when a Task is `Ready`.
    - `on_retry`: What to do when a Task is `Retry`.
    - `on_failed`: What to do when a Task is `Failed`.
    - `should_execute`: Whether a Task should be `Started` or not (`Skipped`).

    Finally, you can put related Tasks under the same `group`.
    """

    pass
