from abc import ABC, abstractmethod

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import List, TypeVar, Union
from zrb.task.any_task import AnyTask

TParallel = TypeVar("TParallel", bound="Parallel")


class AnyParallel(ABC):
    @abstractmethod
    def get_tasks(self) -> List[AnyTask]:
        pass


@typechecked
class Parallel(AnyParallel):
    def __init__(self, *tasks: AnyTask):
        self.__tasks = list(tasks)

    def get_tasks(self) -> List[AnyTask]:
        return self.__tasks

    def __rshift__(
        self, operand: Union[AnyTask, AnyParallel]
    ) -> Union[AnyTask, AnyParallel]:
        if isinstance(operand, AnyTask):
            for task in self.__tasks:
                operand.add_upstream(task)
            return operand
        if isinstance(operand, AnyParallel):
            other_tasks: List[AnyTask] = operand.get_tasks()
            for task in self.__tasks:
                for other_task in other_tasks:
                    other_task.add_upstream(task)
            return operand
