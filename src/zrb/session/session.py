import asyncio
from typing import TYPE_CHECKING, Any, Coroutine

from zrb.context.any_shared_context import AnySharedContext
from zrb.context.context import AnyContext, Context
from zrb.group.any_group import AnyGroup
from zrb.session.any_session import AnySession
from zrb.session_state_logger.any_session_state_logger import AnySessionStateLogger
from zrb.session_state_logger.session_state_logger_factory import session_state_logger
from zrb.task.any_task import AnyTask
from zrb.task_status.task_status import TaskStatus
from zrb.util.cli.style import (
    BLUE,
    BRIGHT_BLUE,
    BRIGHT_CYAN,
    BRIGHT_GREEN,
    BRIGHT_MAGENTA,
    BRIGHT_YELLOW,
    CYAN,
    GREEN,
    ICONS,
    MAGENTA,
    YELLOW,
    remove_style,
)
from zrb.util.group import get_node_path
from zrb.util.string.name import get_random_name
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    from zrb.session_state_log.session_state_log import SessionStateLog


class Session(AnySession):
    def __init__(
        self,
        shared_ctx: AnySharedContext,
        parent: AnySession | None = None,
        root_group: AnyGroup | None = None,
        state_logger: AnySessionStateLogger | None = None,
    ):
        self._name = get_random_name()
        self._root_group = root_group
        self._state_logger = state_logger
        self._task_status: dict[AnyTask, TaskStatus] = {}
        self._upstreams: dict[AnyTask, list[AnyTask]] = {}
        self._downstreams: dict[AnyTask, list[AnyTask]] = {}
        self._context: dict[AnyTask, Context] = {}
        self._shared_ctx = shared_ctx
        self._shared_ctx.set_session(self)
        self._parent = parent
        self._action_coros: dict[AnyTask, asyncio.Task] = {}
        self._monitoring_coros: dict[AnyTask, asyncio.Task] = {}
        self._coros: list[asyncio.Task] = []
        self._colors = [
            GREEN,
            YELLOW,
            BLUE,
            MAGENTA,
            CYAN,
            BRIGHT_GREEN,
            BRIGHT_YELLOW,
            BRIGHT_BLUE,
            BRIGHT_MAGENTA,
            BRIGHT_CYAN,
        ]
        self._icons = ICONS
        self._color_index = 0
        self._icon_index = 0
        self._is_terminated = False
        self._main_task: AnyTask | None = None
        self._main_task_path: list[str] = []

    def __repr__(self):
        class_name = self.__class__.__name__
        name = self.name
        status = self._task_status
        shared_ctx = self.shared_ctx
        return f"<{class_name} name={name} status={status}, shared_ctx={shared_ctx}>"

    @property
    def name(self) -> str:
        return self._name

    @property
    def root_group(self) -> AnyGroup | None:
        return self._root_group

    @property
    def task_names(self) -> list[str]:
        return [task.name for task in self._task_status.keys()]

    @property
    def shared_ctx(self) -> AnySharedContext:
        return self._shared_ctx

    def terminate(self):
        self._is_terminated = True
        for task_status in self._task_status.values():
            task_status.mark_as_terminated()
        for task in self._action_coros.values():
            task.cancel()
        for task in self._monitoring_coros.values():
            task.cancel()
        for task in self._coros:
            task.cancel()

    @property
    def is_terminated(self) -> bool:
        return self._is_terminated

    @property
    def parent(self) -> AnySession | None:
        return self._parent

    @property
    def task_path(self) -> str:
        return self._main_task_path

    @property
    def final_result(self) -> Any:
        xcom: Xcom = self.shared_ctx.xcom[self._main_task.name]
        try:
            return xcom.peek()
        except IndexError:
            return None

    @property
    def state_logger(self) -> AnySessionStateLogger:
        if self._state_logger is None:
            return session_state_logger
        return self._state_logger

    def set_main_task(self, main_task: AnyTask):
        self.register_task(main_task)
        self._main_task = main_task
        main_task_path = get_node_path(self._root_group, main_task)
        self._main_task_path = [] if main_task_path is None else main_task_path

    def as_state_log(self) -> "SessionStateLog":
        from zrb.session_state_log.session_state_log import (
            SessionStateLog,
            TaskStatusHistoryStateLog,
            TaskStatusStateLog,
        )

        task_status_log: dict[str, TaskStatusStateLog] = {}
        log_start_time = ""
        for task, task_status in self._task_status.items():
            history_log = [
                TaskStatusHistoryStateLog(
                    status=status,
                    time=status_at.strftime("%Y-%m-%d %H:%M:%S.%f"),
                )
                for status, status_at in task_status.history
            ]
            if len(history_log) > 0 and (
                log_start_time == "" or history_log[0].time < log_start_time
            ):
                log_start_time = history_log[0].time
            task_status_log[task.name] = TaskStatusStateLog(
                is_started=task_status.is_started,
                is_ready=task_status.is_ready,
                is_completed=task_status.is_completed,
                is_skipped=task_status.is_skipped,
                is_failed=task_status.is_failed,
                is_permanently_failed=task_status.is_permanently_failed,
                is_terminated=task_status.is_terminated,
                history=history_log,
            )
        return SessionStateLog(
            name=self.name,
            start_time=log_start_time,
            main_task_name=self._main_task.name,
            path=self.task_path,
            final_result=(
                remove_style(f"{self.final_result}")
                if self.final_result is not None
                else ""
            ),
            finished=self.is_terminated,
            log=self.shared_ctx.shared_log,
            input=self.shared_ctx.input,
            task_status=task_status_log,
        )

    def get_ctx(self, task: AnyTask) -> AnyContext:
        self._register_single_task(task)
        return self._context[task]

    def defer_monitoring(self, task: AnyTask, coro: Coroutine):
        self._register_single_task(task)
        self._monitoring_coros[task] = coro

    def defer_action(self, task: AnyTask, coro: Coroutine):
        self._register_single_task(task)
        self._action_coros[task] = coro

    def defer_coro(self, coro: Coroutine):
        self._coros.append(coro)
        self._coros = [
            existing_coro for existing_coro in self._coros if not existing_coro.done()
        ]

    async def wait_deferred(self):
        await self._wait_deferred_monitoring()
        await self._wait_deferred_action()
        await asyncio.gather(*self._coros)

    async def _wait_deferred_action(self):
        if len(self._action_coros) == 0:
            return
        task_coros = self._action_coros.values()
        await asyncio.gather(*task_coros)

    async def _wait_deferred_monitoring(self):
        if len(self._monitoring_coros) == 0:
            return
        task_coros = self._monitoring_coros.values()
        await asyncio.gather(*task_coros)

    def register_task(self, task: AnyTask):
        self._register_single_task(task)
        for readiness_check in task.readiness_checks:
            self.register_task(readiness_check)
        for successor in task.successors:
            self.register_task(successor)
        for fallback in task.fallbacks:
            self.register_task(fallback)
        for upstream in task.upstreams:
            self.register_task(upstream)
            if task not in self._downstreams[upstream]:
                self._downstreams[upstream].append(task)
            if upstream not in self._upstreams[task]:
                self._upstreams[task].append(upstream)

    def get_root_tasks(self, task: AnyTask) -> list[AnyTask]:
        root_tasks = []
        upstreams = self._upstreams[task]
        if len(upstreams) == 0:
            root_tasks.append(task)
        else:
            for upstream in upstreams:
                root_tasks += self.get_root_tasks(upstream)
        return list(set(root_tasks))

    def get_next_tasks(self, task: AnyTask) -> list[AnyTask]:
        self._register_single_task(task)
        return self._downstreams.get(task)

    def get_task_status(self, task: AnyTask) -> TaskStatus:
        self._register_single_task(task)
        return self._task_status[task]

    def _register_single_task(self, task: AnyTask):
        if task.name not in self._shared_ctx._xcom:
            self._shared_ctx._xcom[task.name] = Xcom([])
        if task not in self._context:
            self._context[task] = Context(
                shared_ctx=self._shared_ctx,
                task_name=task.name,
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
        if task.color is not None:
            return task.color
        chosen = self._colors[self._color_index]
        self._color_index += 1
        if self._color_index >= len(self._colors):
            self._color_index = 0
        return chosen

    def _get_icon(self, task: AnyTask) -> int:
        if task.icon is not None:
            return task.icon
        chosen = self._icons[self._icon_index]
        self._icon_index += 1
        if self._icon_index >= len(self._icons):
            self._icon_index = 0
        return chosen

    def is_allowed_to_run(self, task: AnyTask):
        if self.is_terminated:
            return False
        self._register_single_task(task)
        task_status = self.get_task_status(task)
        if task_status.is_started or task_status.is_completed:
            return False
        unfulfilled_upstreams = [
            upstream
            for upstream in self._upstreams[task]
            if not self._task_status[upstream].allow_run_downstream
        ]
        return len(unfulfilled_upstreams) == 0
