from typing import List
from typeguard import typechecked
from ..task.base_task import BaseTask


@typechecked
class BaseAction():

    def __init__(self):
        self._tasks: List[BaseTask] = []

    def register(self, task: BaseTask):
        self._tasks.append(task)
