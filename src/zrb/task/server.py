from typing import List, Union, Any, Callable
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any, Callable, Iterable, List, Optional, Union
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
from zrb.task.base_task.base_task import BaseTask
from zrb.task.flow_task import FlowTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput


from zrb.helper.util import to_kebab_case

import asyncio

logger.debug(colored("Loading zrb.task.server", attrs=["dark"]))


@typechecked
class Controller:
    def __init__(
        self,
        name: str,
        trigger: Union[AnyTask, List[AnyTask]],
        action: Union[AnyTask, List[AnyTask]],
    ):
        self._name = name
        self._trigger = trigger
        self._action = action

    def get_env_files(self) -> Iterable[EnvFile]:
        actions = [self._action] if isinstance(self._action, AnyTask) else self._action
        envs = []
        for action in actions:
            envs += action._get_env_files()
        return envs

    def get_envs(self) -> Iterable[Env]:
        actions = [self._action] if isinstance(self._action, AnyTask) else self._action
        envs = []
        for action in actions:
            envs += action._get_envs()
        return envs

    def get_inputs(self) -> Iterable[AnyInput]:
        actions = [self._action] if isinstance(self._action, AnyTask) else self._action
        inputs = []
        for action in actions:
            inputs += action._get_combined_inputs()
        return inputs

    def to_function(self) -> Callable[..., Any]:
        task = self._get_task()
        fn = task.to_function(is_async=True)
        return fn

    def _get_task(self) -> AnyTask:
        kebab_name = to_kebab_case(self._name)
        actions = [self._action] if isinstance(self._action, AnyTask) else self._action
        actions.insert(0, self._get_reschedule_task())
        task: AnyTask = FlowTask(
            name=f"{kebab_name}-flow",
            steps=[
                self._trigger,
                actions
            ]
        )
        return task

    def _get_reschedule_task(self) -> AnyTask:
        kebab_name = to_kebab_case(self._name)

        async def on_ready(task: AnyTask):
            task = self._get_task()
            fn = task.to_function(is_async=True)
            await fn()

        return BaseTask(
            name=f"{kebab_name}-reschedule",
            on_ready=on_ready,
        )


@typechecked
class Server(BaseTask):

    def __init__(
        self,
        name: str,
        controllers: List[Controller],
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
        checkers: Iterable[AnyTask] = [],
        checking_interval: float = 0,
        retry: int = 0,
        retry_interval: float = 1,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
    ):
        inputs, envs, env_files = list(inputs), list(envs), list(env_files)
        for controller in controllers:
            inputs += controller.get_inputs()
            envs += controller.get_envs()
            env_files += controller.get_env_files()
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
            fallbacks=fallbacks,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
        )
        self._controllers = controllers

    async def run(self, *args: Any, **kwargs: Any):
        functions = [
            controller.to_function() for controller in self._controllers
        ]
        await asyncio.gather(*[fn(*args, **kwargs) for fn in functions])

