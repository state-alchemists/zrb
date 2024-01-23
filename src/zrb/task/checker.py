import asyncio

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Callable, Iterable, Optional, Union
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
from zrb.task.base_task.base_task import BaseTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput


@typechecked
class Checker(BaseTask):
    def __init__(
        self,
        name: str = "check",
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
        checking_interval: Union[int, float] = 0.1,
        progress_interval: Union[int, float] = 30,
        expected_result: bool = True,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
    ):
        BaseTask.__init__(
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
            checkers=[],
            checking_interval=checking_interval,
            retry=0,
            retry_interval=0,
            should_execute=should_execute,
        )
        self._progress_interval = progress_interval
        self._expected_result = expected_result
        self._should_show_progress = False

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        wait_time = 0
        while True:
            self._should_show_progress = wait_time >= self._progress_interval
            inspect_result = await self.inspect(*args, **kwargs)
            if inspect_result == self._expected_result:
                return True
            if wait_time >= self._progress_interval:
                wait_time = 0
            await asyncio.sleep(self._checking_interval)
            wait_time += self._checking_interval

    async def inspect(self, *args: Any, **kwargs: Any) -> bool:
        return False

    def show_progress(self, message: str):
        if self._should_show_progress:
            self.print_out_dark(message)
            return
        self.log_debug(message)
