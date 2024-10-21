from typing import Any, Coroutine
from abc import ABC, abstractmethod
from .any_shared_context import AnySharedContext
from .any_context import AnyContext
from ..task.any_base_task import AnyBaseTask


class AnySession(ABC):

    @abstractmethod
    def get_shared_context(self) -> AnySharedContext:
        pass

    @abstractmethod
    def get_context(self, task: AnyBaseTask) -> AnyContext:
        pass

    @abstractmethod
    def register_long_run_coroutine(self, task: AnyBaseTask, coro: Coroutine):
        pass

    @abstractmethod
    async def wait_long_run_coroutines(self):
        pass

    @abstractmethod
    def register_task(self, task: AnyBaseTask):
        pass

    @abstractmethod
    def get_tasks(self) -> list[AnyBaseTask]:
        pass

    @abstractmethod
    def get_downstreams(self, task: AnyBaseTask) -> list[AnyBaseTask]:
        pass

    @abstractmethod
    def mark_task_as_started(self, task: AnyBaseTask):
        pass

    @abstractmethod
    def mark_task_as_completed(self, task: AnyBaseTask):
        pass

    @abstractmethod
    def peek_task_xcom(self, task: AnyBaseTask) -> Any:
        pass

    @abstractmethod
    def append_task_xcom(self, task: AnyBaseTask, value: Any):
        pass

    @abstractmethod
    def is_allowed_to_run(self, task: AnyBaseTask):
        pass
