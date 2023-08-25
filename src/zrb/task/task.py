from zrb.task.base_task import BaseTask
from typeguard import typechecked


@typechecked
class Task(BaseTask):
    '''
    Alias for BaseTask
    '''

    def __repr__(self) -> str:
        return f'<Task name={self._name}>'
