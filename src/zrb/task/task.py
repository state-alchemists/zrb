from typing import Any, Callable
from .base_task import BaseTask
from typeguard import typechecked


@typechecked
class Task(BaseTask):
    '''
    Common Task.
    Exactly the same as BaseTask
    '''

    def should(self, runner: Callable[..., Any]):
        if self._runner is not None:
            raise Exception('Cannot set multiple runners for a single task.')
        self._runner = runner
