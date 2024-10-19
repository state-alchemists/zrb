from typing import Any, Coroutine, TextIO, TypeVar
from abc import ABC, abstractmethod
from collections.abc import Mapping
from ..session.session import Session, TaskStatus
from ..input.any_input import AnyInput
from ..env.any_env import AnyEnv

import asyncio

TAnyTask = TypeVar("TAnyTask", bound="AnyTask")
TState = TypeVar("TState", bound="State")


class AnyTask(ABC):

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    def get_inputs(self) -> list[AnyInput]:
        pass

    @abstractmethod
    def get_envs(self) -> list[AnyEnv]:
        pass

    @abstractmethod
    def get_upstreams(self) -> list[TAnyTask]:
        pass

    @abstractmethod
    def run(self, session: Session | None = None) -> Any:
        pass

    @abstractmethod
    async def async_run(self, session: Session | None = None) -> Any:
        pass

    @abstractmethod
    async def _async_run_root_tasks(self, state: TState):
        pass

    @abstractmethod
    async def _async_run_and_trigger_downstreams(self, state: TState):
        pass

    @abstractmethod
    async def _async_run_action_and_check_readiness(self, state: TState) -> Any:
        pass

    @abstractmethod
    async def _async_run_action(self, session: Session) -> Any:
        pass

    @abstractmethod
    async def print(
        self,
        *values: object,
        sep: str | None,
        end: str | None,
        files: TextIO | None,
        flush: bool
    ):
        pass


class State():
    def __init__(self, session: Session):
        self._task_status: Mapping[AnyTask, TaskStatus] = {}
        self._upstreams: Mapping[AnyTask, list[AnyTask]] = {}
        self._downstreams: Mapping[AnyTask, list[AnyTask]] = {}
        self._session = session
        self._long_run_coros: list[Coroutine] = []

    def get_session(self):
        return self._session

    def register_long_run_coroutine(self, coro: Coroutine):
        self._long_run_coros.append(coro)

    async def wait_long_run_coroutines(self):
        if len(self._long_run_coros) == 0:
            return
        await asyncio.gather(*self._long_run_coros)

    def register_task(self, task: AnyTask):
        if task not in self._task_status:
            self._task_status[task] = TaskStatus()
        if task not in self._downstreams:
            self._downstreams[task] = []
        if task not in self._upstreams:
            self._upstreams[task] = []

    def register_upstreams(self, task: AnyTask, upstreams: list[AnyTask]):
        self.register_task(task)
        for upstream in upstreams:
            self.register_upstreams(upstream, upstream.get_upstreams())
            if task not in self._downstreams[upstream]:
                self._downstreams[upstream].append(task)
            if upstream not in self._upstreams[task]:
                self._upstreams[task].append(upstream)

    def get_tasks(self) -> list[AnyTask]:
        return list(self._task_status.keys())

    def get_downstreams(self, task: AnyTask) -> list[AnyTask]:
        return self._downstreams.get(task)

    def mark_task_as_started(self, task: AnyTask):
        self.register_task(task)
        self._task_status[task].start()

    def mark_task_as_completed(self, task: AnyTask):
        self.register_task(task)
        self._task_status[task].complete()

    def is_allowed_to_run(self, task: AnyTask):
        task_status = self._task_status[task]
        if task_status.is_started() or task_status.is_completed():
            return False
        incomplete_upstreams = [
            upstream for upstream in self._upstreams[task]
            if not self._task_status[upstream].is_completed()
        ]
        return len(incomplete_upstreams) == 0

    def is_completed(self):
        incomplete_tasks = [
            task for task in self._task_status
            if not self._task_status.get(task).is_completed()
        ]
        return len(incomplete_tasks) == 0
