from typing import List
from ..task.base_task import BaseTask


class BaseAction():
    tasks: List[BaseTask] = []

    def register(self, task: BaseTask):
        self.tasks.append(task)
