from typing import List
from pydantic import BaseModel
from ..task.base_task import BaseTask


class BaseAction(BaseModel):
    tasks: List[BaseTask] = []

    def register(self, task: BaseTask):
        self.tasks.append(task)
