from typing import Iterable
from typeguard import typechecked
from ..task.any_task import AnyTask


@typechecked
class BaseAction():

    def __init__(self):
        self._tasks: Iterable[AnyTask] = []

    def register(self, task: AnyTask):
        self._tasks.append(task)
