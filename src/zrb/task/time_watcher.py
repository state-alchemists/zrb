import datetime

import croniter

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import (
    Any,
    Callable,
    Iterable,
    JinjaTemplate,
    Optional,
    TypeVar,
    Union,
)
from zrb.task.any_task import AnyTask
from zrb.task.any_task_event_handler import (
    OnFailed,
    OnReady,
    OnRetry,
    OnSkipped,
    OnStarted,
    OnTriggered,
    OnWaiting,
)
from zrb.task.checker import Checker
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

TTimeWatcher = TypeVar("TTimeWatcher", bound="TimeWatcher")


@typechecked
class TimeWatcher(Checker):
    """
    TimeWatcher will wait for any changes specified on  path.

    Once the changes detected, TimeWatcher will be completed
    and <task-name>.scheduled-time xcom will be set.
    """

    def __init__(
        self,
        name: str = "watch-path",
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = "",
        upstreams: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        schedule: JinjaTemplate = "",
        checking_interval: Union[int, float] = 1,
        progress_interval: Union[int, float] = 30,
        should_execute: Union[bool, JinjaTemplate, Callable[..., bool]] = True,
    ):
        Checker.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            upstreams=upstreams,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checking_interval=checking_interval,
            progress_interval=progress_interval,
            should_execute=should_execute,
        )
        self._schedule = schedule
        self._scheduled_time: Optional[datetime.datetime] = None
        self._rendered_schedule: str = ""

    def copy(self) -> TTimeWatcher:
        return super().copy()

    def to_function(
        self,
        env_prefix: str = "",
        raise_error: bool = True,
        is_async: bool = False,
        show_done_info: bool = True,
    ) -> Callable[..., bool]:
        return super().to_function(env_prefix, raise_error, is_async, show_done_info)

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        self._rendered_schedule = self.render_str(self._schedule)
        margin = datetime.timedelta(seconds=0.001)
        slightly_before_check_time = datetime.datetime.now() - margin
        cron = croniter.croniter(self._rendered_schedule, slightly_before_check_time)
        self._scheduled_time = cron.get_next(datetime.datetime)
        self.set_task_xcom(key="scheduled-time", value=self._scheduled_time)
        return await super().run(*args, **kwargs)

    async def inspect(self, *args: Any, **kwargs: Any) -> bool:
        label = f"Watching {self._rendered_schedule}"
        now = datetime.datetime.now()
        if now > self._scheduled_time:
            self.print_out_dark(f"{label} (Meet {self._scheduled_time})")
            return True
        self.show_progress(f"{label} (Waiting for {self._scheduled_time})")
        return False
