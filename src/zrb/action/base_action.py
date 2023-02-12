from typing import Iterable
from typeguard import typechecked
from ..task.base_task import BaseTask


@typechecked
class BaseAction():

    def __init__(self):
        self._tasks: Iterable[BaseTask] = []

    def register(self, task: BaseTask):
        self._tasks.append(task)
