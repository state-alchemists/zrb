from typing import List
from pydantic import BaseModel
from ..task.base_task import BaseTask


class BaseAction(BaseModel):
    tasks: List[BaseTask] = []

    class Config:
        arbitrary_types_allowed = True

    def register(self, task: BaseTask):
        self.tasks.append(task)
