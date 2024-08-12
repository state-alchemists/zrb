import asyncio
import datetime
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional, TypeVar, Union

import croniter

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import JinjaTemplate
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
from zrb.task.watcher import Watcher
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.time_watcher", attrs=["dark"]))

TTimeWatcher = TypeVar("TTimeWatcher", bound="TimeWatcher")


@typechecked
class TimeWatcher(Watcher):
    """
    TimeWatcher will wait for any changes specified on  path.

    Once the changes detected, TimeWatcher will be completed
    and <task-name>.scheduled-time xcom will be set.
    """

    __scheduled_times: Mapping[str, Mapping[str, datetime.datetime]] = {}

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
        fallbacks: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        schedule: JinjaTemplate = "",
        checking_interval: Union[int, float] = 0.05,
        progress_interval: Union[int, float] = 30,
        should_execute: Union[bool, JinjaTemplate, Callable[..., bool]] = True,
    ):
        Watcher.__init__(
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
            fallbacks=fallbacks,
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
        self._rendered_schedule: str = ""

    def copy(self) -> TTimeWatcher:
        return super().copy()

    def to_function(
        self,
        env_prefix: str = "",
        raise_error: bool = True,
        is_async: bool = False,
        show_done_info: bool = True,
        should_clear_xcom: bool = False,
        should_stop_looper: bool = False,
    ) -> Callable[..., bool]:
        return super().to_function(
            env_prefix=env_prefix,
            raise_error=raise_error,
            is_async=is_async,
            show_done_info=show_done_info,
            should_clear_xcom=should_clear_xcom,
            should_stop_looper=should_stop_looper,
        )

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        self._rendered_schedule = self.render_str(self._schedule)
        identifier = self.get_identifier()
        if identifier not in self.__scheduled_times:
            self.__scheduled_times[identifier] = self._get_next_schedule_time()
        return await super().run(*args, **kwargs)

    def create_loop_inspector(self) -> Callable[..., Optional[bool]]:
        async def loop_inspect() -> bool:
            await asyncio.sleep(self._checking_interval)
            label = f"Watching {self._rendered_schedule}"
            identifier = self.get_identifier()
            scheduled_time = self.__scheduled_times[identifier]
            self.set_task_xcom(key="scheduled-time", value=scheduled_time)
            now = datetime.datetime.now()
            if now > scheduled_time:
                self.print_out_dark(f"{label} (Meet {scheduled_time})")
                self.__scheduled_times[identifier] = self._get_next_schedule_time()
                return True
            self.show_progress(f"{label} (Waiting for {scheduled_time})")
            return False

        return loop_inspect

    def _get_next_schedule_time(self) -> datetime.datetime:
        cron = self._get_cron()
        return cron.get_next(datetime.datetime)

    def _get_cron(self) -> Any:
        margin = datetime.timedelta(seconds=self._checking_interval / 2.0)
        slightly_before_now = datetime.datetime.now() - margin
        cron = croniter.croniter(self._rendered_schedule, slightly_before_now)
        return cron
