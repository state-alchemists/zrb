import asyncio
import copy
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional, Union

from zrb.helper.accessories.color import colored
from zrb.helper.accessories.name import get_random_name
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.util import to_kebab_case
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

logger.debug(colored("Loading zrb.task.server", attrs=["dark"]))


@typechecked
class Controller:
    def __init__(
        self,
        trigger: Union[AnyTask, list[AnyTask]],
        action: Union[AnyTask, list[AnyTask]],
        name: Optional[str] = None,
    ):
        self._name = get_random_name() if name is None else name
        self._triggers = self._to_task_list(trigger)
        self._actions = self._to_task_list(action)
        self._args: list[Any] = []
        self._kwargs: Mapping[str, Any] = {}
        self._inputs: list[AnyInput] = []
        self._envs: list[Env] = []
        self._env_files: list[EnvFile] = []

    def set_args(self, args: list[Any]):
        self._args = args

    def set_kwargs(self, kwargs: Mapping[str, Any]):
        self._kwargs = kwargs

    def set_inputs(self, inputs: list[AnyInput]):
        self._inputs = inputs

    def set_envs(self, envs: list[Env]):
        self._envs = envs

    def set_env_files(self, env_files: list[EnvFile]):
        self._env_files = env_files

    def get_original_env_files(self) -> Iterable[EnvFile]:
        env_files = []
        for trigger in self._triggers:
            env_files += trigger._get_env_files()
        for action in self._actions:
            env_files += action._get_env_files()
        return env_files

    def get_original_envs(self) -> Iterable[Env]:
        envs = []
        for trigger in self._triggers:
            envs += trigger._get_envs()
        for action in self._actions:
            envs += action._get_envs()
        return envs

    def get_original_inputs(self) -> Iterable[AnyInput]:
        inputs = []
        for trigger in self._triggers:
            inputs += trigger._get_combined_inputs()
        for action in self._actions:
            inputs += action._get_combined_inputs()
        return inputs

    def to_function(self) -> Callable[..., Any]:
        task = self._get_task()

        async def fn() -> Any:
            task.print_out_dark(f"Starting controller: {self._name}")
            task_fn = task.to_function(is_async=True)
            return await task_fn(*self._args, **self._kwargs)

        return fn

    def _to_task_list(self, tasks: Union[AnyTask, list[AnyTask]]) -> list[AnyTask]:
        if isinstance(tasks, AnyTask):
            return [tasks.copy()]
        return [task.copy() for task in tasks]

    def _get_task(self) -> AnyTask:
        actions = [action.copy() for action in self._actions]
        actions.insert(0, self._get_remonitor_task())
        triggers = [trigger.copy() for trigger in self._triggers]
        task: AnyTask = FlowTask(
            name=to_kebab_case(self._name),
            inputs=self._inputs,
            envs=self._envs,
            env_files=self._env_files,
            steps=[triggers, actions],
        )
        return task

    def _get_remonitor_task(self) -> AnyTask:
        async def on_ready(task: AnyTask):
            task = self._get_task()
            fn = task.to_function(is_async=True)
            await fn()

        return BaseTask(
            name=f"monitor-{to_kebab_case(self._name)}",
            on_ready=on_ready,
        )


@typechecked
class Server(BaseTask):

    def __init__(
        self,
        name: str,
        controllers: Iterable[Controller],
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
        checking_interval: Union[int, float] = 0.05,
        retry: int = 0,
        retry_interval: Union[int, float] = 1,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
    ):
        inputs, envs, env_files = list(inputs), list(envs), list(env_files)
        for controller in controllers:
            controller_cp = copy.deepcopy(controller)
            inputs += controller_cp.get_original_inputs()
            envs += controller_cp.get_original_envs()
            env_files += controller_cp.get_original_env_files()
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
        self._controllers = list(controllers)

    async def run(self, *args: Any, **kwargs: Any):
        for controller in self._controllers:
            controller.set_envs(self._get_envs())
            controller.set_env_files(self._get_env_files())
            controller.set_inputs(self._get_inputs())
            controller.set_args(args)
            controller.set_kwargs(kwargs)
        functions = [controller.to_function() for controller in self._controllers]
        await asyncio.gather(*[fn() for fn in functions])
