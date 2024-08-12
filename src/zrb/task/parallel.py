from abc import ABC, abstractmethod
from typing import TypeVar, Union

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.task.any_task import AnyTask

logger.debug(colored("Loading zrb.task.parallel", attrs=["dark"]))

TParallel = TypeVar("TParallel", bound="Parallel")


class AnyParallel(ABC):
    @abstractmethod
    def get_tasks(self) -> list[AnyTask]:
        pass


@typechecked
class Parallel(AnyParallel):
    def __init__(self, *tasks: AnyTask):
        self.__tasks = list(tasks)

    def get_tasks(self) -> list[AnyTask]:
        return self.__tasks

    def __rshift__(
        self, operand: Union[AnyTask, AnyParallel]
    ) -> Union[AnyTask, AnyParallel]:
        if isinstance(operand, AnyTask):
            for task in self.__tasks:
                operand.add_upstream(task)
            return operand
        if isinstance(operand, AnyParallel):
            other_tasks: list[AnyTask] = operand.get_tasks()
            for task in self.__tasks:
                for other_task in other_tasks:
                    other_task.add_upstream(task)
            return operand
