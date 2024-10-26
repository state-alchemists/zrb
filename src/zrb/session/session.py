from typing import Any, Coroutine
from collections.abc import Mapping
from .any_session import AnySession
from ..context.any_shared_context import AnySharedContext
from ..context.context import AnyContext
from ..context.context import Context
from ..task_status.task_status import TaskStatus
from ..xcom.xcom import Xcom
from ..task.any_task import AnyTask
from ..util.cli.style import GREEN, YELLOW, BLUE, MAGENTA, CYAN, ICONS

import asyncio


class Session(AnySession):
    def __init__(self, shared_context: AnySharedContext):
        self._task_status: Mapping[AnyTask, TaskStatus] = {}
        self._upstreams: Mapping[AnyTask, list[AnyTask]] = {}
        self._downstreams: Mapping[AnyTask, list[AnyTask]] = {}
        self._context: Mapping[AnyTask, Context] = {}
        self._shared_ctx = shared_context
        self._task_coros: Mapping[AnyTask, Coroutine] = {}
        self._colors = [GREEN, YELLOW, BLUE, MAGENTA, CYAN]
        self._icons = ICONS
        self._color_index = 0
        self._icon_index = 0
        self._is_terminated = False

    def __repr__(self):
        class_name = self.__class__.__name__
        return f"<{class_name} status={self._task_status}, shared_ctx={self._shared_ctx}>"

    def terminate(self):
        self._is_terminated = True

    @property
    def is_terminated(self) -> bool:
        return self._is_terminated

    def get_shared_ctx(self) -> AnySharedContext:
        return self._shared_ctx

    def get_ctx(self, task: AnyTask) -> AnyContext:
        self._register_single_task(task)
        return self._context[task]

    def defer_task_coroutine(self, task: AnyTask, coro: Coroutine):
        self._register_single_task(task)
        self._task_coros[task] = coro

    async def wait_deffered_task_coroutines(self):
        if len(self._task_coros) == 0:
            return
        tasks = self._task_coros.keys()
        task_coros = self._task_coros.values()
        results = await asyncio.gather(*task_coros)
        for index, task in enumerate(tasks):
            self.mark_task_as_completed(task)
            self.append_task_xcom(task, results[index])

    def register_task(self, task: AnyTask):
        self._register_single_task(task)
        for readiness_check in task.get_readiness_checks():
            self.register_task(readiness_check)
        for upstream in task.get_upstreams():
            self.register_task(upstream)
            if task not in self._downstreams[upstream]:
                self._downstreams[upstream].append(task)
            if upstream not in self._upstreams[task]:
                self._upstreams[task].append(upstream)

    def get_tasks(self) -> list[AnyTask]:
        return list(self._task_status.keys())

    def get_next_tasks(self, task: AnyTask) -> list[AnyTask]:
        self._register_single_task(task)
        return self._downstreams.get(task)

    def get_task_status(self, task: AnyTask) -> TaskStatus:
        self._register_single_task(task)
        return self._task_status[task]

    def peek_task_xcom(self, task: AnyTask) -> Any:
        self._register_single_task(task)
        task_name = task.get_name()
        if task_name not in self._shared_ctx._xcom:
            return None
        xcom = self._shared_ctx._xcom[task_name]
        if len(xcom) > 0:
            return xcom[0]
        return None

    def append_task_xcom(self, task: AnyTask, value: Any):
        self._register_single_task(task)
        self._shared_ctx._xcom[task.get_name()].append(value)

    def _register_single_task(self, task: AnyTask):
        if task.get_name() not in self._shared_ctx._xcom:
            self._shared_ctx._xcom[task.get_name()] = Xcom([])
        if task not in self._context:
            self._context[task] = Context(
                shared_context=self._shared_ctx,
                task_name=task.get_name(),
                color=self._get_color(task),
                icon=self._get_icon(task),
            )
        if task not in self._task_status:
            self._task_status[task] = TaskStatus()
        if task not in self._downstreams:
            self._downstreams[task] = []
        if task not in self._upstreams:
            self._upstreams[task] = []

    def _get_color(self, task: AnyTask) -> int:
        if task.get_color() is not None:
            return task.get_color()
        chosen = self._colors[self._color_index]
        self._color_index += 1
        if self._color_index >= len(self._colors):
            self._color_index = 0
        return chosen

    def _get_icon(self, task: AnyTask) -> int:
        if task.get_icon() is not None:
            return task.get_icon()
        chosen = self._icons[self._icon_index]
        self._icon_index += 1
        if self._icon_index >= len(self._icons):
            self._icon_index = 0
        return chosen

    def is_allowed_to_run(self, task: AnyTask):
        if self.is_terminated:
            return False
        self._register_single_task(task)
        task_status = self._task_status[task]
        if task_status.is_started or task_status.is_completed:
            return False
        unfulfilled_upstreams = [
            upstream for upstream in self._upstreams[task]
            if not self._task_status[upstream].allow_run_downstream
        ]
        return len(unfulfilled_upstreams) == 0
