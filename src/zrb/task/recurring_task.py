from zrb.helper.typing import (
    Any, Callable, Iterable, Mapping, Optional, Union
)
from zrb.helper.typecheck import typechecked
from zrb.task.base_task.base_task import BaseTask
from zrb.task.any_task import AnyTask
from zrb.task.any_task_event_handler import (
    OnTriggered, OnWaiting, OnSkipped, OnStarted, OnReady, OnRetry, OnFailed
)
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

import asyncio
import copy


@typechecked
class RecurringTask(BaseTask):

    def __init__(
        self,
        name: str,
        task: AnyTask,
        triggers: Iterable[AnyTask] = [],
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        upstreams: Iterable[AnyTask] = [],
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
        return_upstream_result: bool = False
    ):
        inputs = list(inputs) + task._get_inputs()
        envs = list(envs) + task._get_envs()
        env_files = list(env_files) + task._get_env_files()
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
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
        )
        self._task = task
        self._triggers = triggers

    async def _set_keyval(self, kwargs: Mapping[str, Any], env_prefix: str):
        await super()._set_keyval(kwargs=kwargs, env_prefix=env_prefix)
        new_kwargs = copy.deepcopy(kwargs)
        new_kwargs.update(self.get_input_map())
        trigger_coroutines = []
        for trigger in self._triggers:
            trigger.add_input(*self._get_inputs())
            trigger.add_env(*self._get_envs())
            trigger_coroutines.append(asyncio.create_task(
                trigger._set_keyval(
                    kwargs=new_kwargs, env_prefix=env_prefix
                )
            ))
        await asyncio.gather(*trigger_coroutines)

    async def run(self, *args: Any, **kwargs: Any):
        task_kwargs = {
            key: kwargs[key]
            for key in kwargs if key not in ['_task']
        }
        while True:
            # Create trigger functions
            trigger_functions = []
            for trigger in self._triggers:
                trigger_function = trigger.copy().to_function(
                    is_async=True, raise_error=False, show_done_info=False
                )
                trigger_functions.append(asyncio.create_task(
                    trigger_function(*args, **task_kwargs)
                ))
            # Wait for the first task to complete
            self.print_out_dark('Waiting for trigger')
            _, pending = await asyncio.wait(
                trigger_functions, return_when=asyncio.FIRST_COMPLETED
            )
            # Cancel the remaining tasks
            for task in pending:
                try:
                    task.cancel()
                except Exception as e:
                    self.print_err(e)
            # Run the task
            fn = self._task.copy().to_function(
                is_async=True, raise_error=False, show_done_info=False
            )
            self.print_out_dark('Executing the task')
            asyncio.create_task(fn(*args, **task_kwargs))
            self._play_bell()
