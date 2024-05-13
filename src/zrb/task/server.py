import asyncio

from zrb.helper.accessories.color import colored
from zrb.helper.accessories.name import get_random_name
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Callable, Iterable, List, Mapping, Optional, Union
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
        trigger: Union[AnyTask, List[AnyTask]],
        action: Union[AnyTask, List[AnyTask]],
        name: Optional[str] = None,
    ):
        self._id = get_random_name()
        self._name = get_random_name() if name is None else name
        self._triggers = [trigger] if isinstance(trigger, AnyTask) else trigger
        self._actions = [action] if isinstance(action, AnyTask) else action
        self._args: List[Any] = []
        self._kwargs: Mapping[str, Any] = {}
        self._inputs: List[AnyInput] = []
        self._envs: List[Env] = []
        self._env_files: List[EnvFile] = []

    def set_args(self, args: List[Any]):
        self._args = args

    def set_kwargs(self, kwargs: Mapping[str, Any]):
        self._kwargs = kwargs

    def set_inputs(self, inputs: List[AnyInput]):
        self._inputs = inputs

    def set_envs(self, envs: List[Env]):
        self._envs = envs

    def set_env_files(self, env_files: List[EnvFile]):
        self._env_files = env_files

    def get_sub_env_files(self) -> Iterable[EnvFile]:
        env_files = []
        for trigger in self._triggers:
            env_files += trigger.copy()._get_env_files()
        for action in self._actions:
            env_files += action.copy()._get_env_files()
        return env_files

    def get_sub_envs(self) -> Iterable[Env]:
        envs = []
        for trigger in self._triggers:
            envs += trigger.copy()._get_envs()
        for action in self._actions:
            envs += action.copy()._get_envs()
        return envs

    def get_sub_inputs(self) -> Iterable[AnyInput]:
        inputs = []
        for trigger in self._triggers:
            inputs += trigger.copy()._get_combined_inputs()
        for action in self._actions:
            inputs += action.copy()._get_combined_inputs()
        return inputs

    def to_function(self) -> Callable[..., Any]:
        task = self._get_task()

        async def fn() -> Any:
            task_fn = task.to_function(is_async=True)
            return await task_fn(*self._args, **self._kwargs)

        return fn

    def _get_task(self) -> AnyTask:
        actions = list(self._actions)
        actions.insert(0, self._get_remonitor_task())
        task: AnyTask = FlowTask(
            name=to_kebab_case(self._name),
            inputs=self._inputs,
            envs=self._envs,
            env_files=self._env_files,
            steps=[self._triggers, actions],
        )
        sub_execution_id = get_random_name()
        task._set_execution_id(f"{self._id}:{sub_execution_id}")
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
            inputs += controller.get_sub_inputs()
            envs += controller.get_sub_envs()
            env_files += controller.get_sub_env_files()
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
        for controller in self._controllers:
            controller.set_envs(self._get_envs())
            controller.set_env_files(self._get_env_files())
            controller.set_inputs(self._get_inputs())
            controller.set_args(args)
            controller.set_kwargs(kwargs)
        functions = [controller.to_function() for controller in self._controllers]
        await asyncio.gather(*[fn() for fn in functions])
