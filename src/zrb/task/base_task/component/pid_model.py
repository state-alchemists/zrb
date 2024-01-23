import os

from zrb.helper.typecheck import typechecked


@typechecked
class PidModel:
    def __init__(self):
        self.__task_pid: int = os.getpid()

    def _set_task_pid(self, pid: int):
        self.__task_pid = pid

    def _get_task_pid(self) -> int:
        return self.__task_pid
