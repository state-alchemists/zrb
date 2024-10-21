from typing import Any, Coroutine
from collections.abc import Mapping
from collections import deque
from .any_session import AnySession
from .any_shared_context import AnySharedContext
from .context import AnyContext
from .context import Context
from .task_status import TaskStatus
from ..task.any_base_task import AnyBaseTask
from ..util.cli.style import GREEN, YELLOW, BLUE, MAGENTA, CYAN, ICONS

import asyncio


class Session(AnySession):
    def __init__(self, shared_context: AnySharedContext):
        self._task_status: Mapping[AnyBaseTask, TaskStatus] = {}
        self._upstreams: Mapping[AnyBaseTask, list[AnyBaseTask]] = {}
        self._downstreams: Mapping[AnyBaseTask, list[AnyBaseTask]] = {}
        self._context: Mapping[AnyBaseTask, Context] = {}
        self._shared_context = shared_context
        self._long_run_coros: Mapping[AnyBaseTask, Coroutine] = {}
        self._colors = [GREEN, YELLOW, BLUE, MAGENTA, CYAN]
        self._icons = ICONS
        self._color_index = 0
        self._icon_index = 0

    def get_shared_context(self) -> AnySharedContext:
        return self._shared_context

    def get_context(self, task: AnyBaseTask) -> AnyContext:
        return self._context[task]

    def register_long_run_coroutine(self, task: AnyBaseTask, coro: Coroutine):
        self._long_run_coros[task] = coro

    async def wait_long_run_coroutines(self):
        if len(self._long_run_coros) == 0:
            return
        tasks = self._long_run_coros.keys()
        coros = self._long_run_coros.values()
        results = await asyncio.gather(*coros)
        for index, task in enumerate(tasks):
            self.mark_task_as_completed(task)
            self.append_task_xcom(task, results[index])

    def register_task(self, task: AnyBaseTask):
        self._register_single_task(task)
        for readiness_check in task.get_readiness_checks():
            self.register_task(readiness_check)
        for upstream in task.get_upstreams():
            self.register_task(upstream)
            if task not in self._downstreams[upstream]:
                self._downstreams[upstream].append(task)
            if upstream not in self._upstreams[task]:
                self._upstreams[task].append(upstream)

    def get_tasks(self) -> list[AnyBaseTask]:
        return list(self._task_status.keys())

    def get_downstreams(self, task: AnyBaseTask) -> list[AnyBaseTask]:
        return self._downstreams.get(task)

    def mark_task_as_started(self, task: AnyBaseTask):
        self._register_single_task(task)
        self._task_status[task].mark_as_started()

    def mark_task_as_completed(self, task: AnyBaseTask):
        self._register_single_task(task)
        self._task_status[task].mark_as_completed()

    def peek_task_xcom(self, task: AnyBaseTask) -> Any:
        task_name = task.get_name()
        if task_name not in self._shared_context.xcoms:
            return None
        xcom = self._shared_context.xcoms[task_name]
        if len(xcom) > 0:
            return xcom[0]
        return None

    def append_task_xcom(self, task: AnyBaseTask, value: Any):
        self._init_xcom(task)
        self._shared_context.xcoms[task.get_name()].append(value)

    def _register_single_task(self, task: AnyBaseTask):
        self._init_xcom(task)
        if task not in self._context:
            self._context[task] = Context(
                shared_context=self._shared_context,
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

    def _init_xcom(self, task: AnyBaseTask):
        task_name = task.get_name()
        if task_name not in self._shared_context.xcoms:
            self._shared_context.xcoms[task_name] = deque([])

    def _get_color(self, task: AnyBaseTask) -> int:
        task_color = task.get_color()
        if task_color is not None:
            return task_color
        chosen = self._colors[self._color_index]
        self._color_index += 1
        if self._color_index >= len(self._colors):
            self._color_index = 0
        return chosen

    def _get_icon(self, task: AnyBaseTask) -> int:
        task_icon = task.get_icon()
        if task_icon is not None:
            return task_icon
        chosen = self._icons[self._icon_index]
        self._icon_index += 1
        if self._icon_index >= len(self._icons):
            self._icon_index = 0
        return chosen

    def is_allowed_to_run(self, task: AnyBaseTask):
        task_status = self._task_status[task]
        if task_status.is_started() or task_status.is_completed():
            return False
        incomplete_upstreams = [
            upstream for upstream in self._upstreams[task]
            if not self._task_status[upstream].is_completed()
        ]
        return len(incomplete_upstreams) == 0
