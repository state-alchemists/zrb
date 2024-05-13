from zrb.helper.accessories.color import colored
from zrb.helper.accessories.name import get_random_name
from zrb.helper.callable import run_async
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import (
    Any, Callable, Iterable, List, Mapping, Optional, Union
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

import asyncio

logger.debug(colored("Loading zrb.task.watcher", attrs=["dark"]))


class Looper():
    def __init__(self):
        self._queue: Mapping[str, List[Optional[bool]]] = {}

    async def pop(self, identifier: str) -> Optional[bool]:
        if identifier not in self._queue or len(self._queue[identifier]) == 0:
            return None
        return self._queue[identifier].pop(0)

    def is_registered(self, identifier: str) -> bool:
        return identifier in self._queue

    async def register(
        self, identifier: str, function: Callable[..., Optional[bool]]
    ):
        if identifier in self._queue:
            return
        self._queue[identifier] = []
        while True:
            try:
                result = await run_async(function)
                if result is not None:
                    if not result:
                        continue
                    self._queue[identifier].append(result)
            except KeyboardInterrupt:
                break


@typechecked
class Watcher(Checker):
    __looper = Looper()

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
        checking_interval: Union[int, float] = 0.1,
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
        if not self.__looper.is_registered(self._identifier):
            asyncio.create_task(
                self.__looper.register(
                    self._identifier, self.create_loop_inspector()
                )
            )
        return await super().run(*args, **kwargs)

    async def inspect(self, *args, **kwargs: Any) -> Optional[bool]:
        result = await self.__looper.pop(self._identifier)
        return result

    def create_loop_inspector(self) -> Callable[..., Optional[bool]]:
        def loop_inspect() -> Optional[bool]:
            return None
        return loop_inspect

