from zrb.task.base_task.base_task import BaseTask
from zrb.helper.typecheck import typechecked


@typechecked
class Task(BaseTask):
    '''
    Alias for BaseTask
    '''

    def __repr__(self) -> str:
        return f'<Task name={self._name}>'
