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

    Moreover, you can define Task dependencies by specifying its `upstreams` or by using shift-right operator.

    Every Zrb Task has its life-cycle state:
    - `Triggered`: The Task is triggered (either by the user or by the other Task).
    - `Waiting`: Zrb has already triggered the Task. The Task is now waiting for all its upstreams to be ready.
    - `Skipped`: Task upstreams are ready, but the Task is not executed and will immediately enter the `Ready` state.
    - `Started`: The upstreams are ready, and Zrb is now starting the Task execution.
    - `Failed`: Zrb failed to execute the Task. It will enter the `Retry` state if the current attempt does not exceed the maximum attempt.
    - `Retry`: The task has already entered the `Failed` state. Now, Zrb will try to start the Task execution.
    - `Ready`: The task is ready.

    There are several configurations related to Task's life cycle:
    - `retry`: Maximum retry attempt.
    - `retry_interval`: The duration is to wait before Zrb starts the next attempt.
    - `fallbacks`: Action to take if the Task has failed for good.
    - `checkers`: How to determine if a Task is `Ready`.
    - `checking_interval`: The duration to wait before Zrb checks for the Task's readiness.
    - `run`: Action to do when Zrb executes the Task.
    - `on_triggered`: Action to do when a Task is `Triggered`.
    - `on_waiting`: Action to do when a Task is `Waiting`.
    - `on_skipped`: Action to do when a Task is `Skipped`.
    - `on_started`: Action to do when a Task is `Started`.
    - `on_ready`: Action to do when a Task is `Ready`.
    - `on_retry`: Action to do when a Task is `Retry`.
    - `on_failed`: Action to do when a Task is `Failed`.
    - `should_execute`: Condition to determine whether a Task should be `Started` or `Skipped`.

    Finally, you can put related Tasks under the same `group`.
    """

    pass
