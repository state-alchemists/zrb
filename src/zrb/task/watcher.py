import asyncio
from collections.abc import Callable, Iterable
from typing import Any, Optional, Union

from zrb.helper.accessories.color import colored
from zrb.helper.accessories.name import get_random_name
from zrb.helper.callable import run_async
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
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
from zrb.task.looper import looper
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.watcher", attrs=["dark"]))


@typechecked
class Watcher(Checker):
    __looper = looper

    def __init__(
        self,
        name: str = "watch",
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
        checking_interval: Union[int, float] = 0.05,
        progress_interval: Union[int, float] = 30,
        expected_result: bool = True,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
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
            fallbacks=fallbacks,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checking_interval=checking_interval,
            should_execute=should_execute,
            progress_interval=progress_interval,
            expected_result=expected_result,
        )
        self._identifier = get_random_name()

    def get_identifier(self):
        return self._identifier

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        if not looper.is_registered(self._identifier):
            asyncio.create_task(
                run_async(
                    looper.register, self._identifier, self.create_loop_inspector()
                )
            )
        return await super().run(*args, **kwargs)

    async def inspect(self, *args, **kwargs: Any) -> Optional[bool]:
        result = await looper.pop(self._identifier)
        return result

    def create_loop_inspector(self) -> Callable[..., Optional[bool]]:
        def loop_inspect() -> Optional[bool]:
            return None

        return loop_inspect
