import asyncio
import copy

from zrb.helper.accessories.name import get_random_name
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Callable, Iterable, List, Mapping, Optional, Union
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


class RunConfig:
    def __init__(
        self,
        fn: Callable[..., Any],
        args: List[Any],
        kwargs: Mapping[Any, Any],
        execution_id: str,
    ):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.execution_id = execution_id

    async def run(self):
        return await self.fn(*self.args, **self.kwargs)


@typechecked
class RecurringTask(BaseTask):
    """
    A class representing a recurring task that is triggered based on
    specified conditions.

    Examples:

        >>> from zrb import RecurringTask
    """

    def __init__(
        self,
        name: str,
        task: AnyTask,
        triggers: Iterable[AnyTask] = [],
        single_execution: bool = False,
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
        checkers: Iterable[AnyTask] = [],
        checking_interval: float = 0,
        retry: int = 0,
        retry_interval: float = 1,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
    ):
        self._task: AnyTask = task.copy()
        inputs = list(inputs) + self._task._get_combined_inputs()
        envs = list(envs) + self._task._get_envs()
        env_files = list(env_files) + self._task._get_env_files()
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
        self._triggers: List[AnyTask] = [trigger.copy() for trigger in triggers]
        self._run_configs: List[RunConfig] = []
        self._single_execution = single_execution

    async def _set_keyval(self, kwargs: Mapping[str, Any], env_prefix: str):
        await super()._set_keyval(kwargs=kwargs, env_prefix=env_prefix)
        new_kwargs = copy.deepcopy(kwargs)
        new_kwargs.update(self.get_input_map())
        trigger_coroutines = []
        for trigger in self._triggers:
            trigger.add_input(*self._get_inputs())
            trigger.add_env(*self._get_envs())
            trigger_coroutines.append(
                asyncio.create_task(
                    trigger._set_keyval(kwargs=new_kwargs, env_prefix=env_prefix)
                )
            )
        await asyncio.gather(*trigger_coroutines)

    async def run(self, *args: Any, **kwargs: Any):
        await asyncio.gather(
            asyncio.create_task(self.__check_trigger(*args, **kwargs)),
            asyncio.create_task(self.__run_from_queue()),
        )

    async def __check_trigger(self, *args: Any, **kwargs: Any):
        task_kwargs = {key: kwargs[key] for key in kwargs if key not in ["_task"]}
        is_first_time = True
        while True:
            execution_id = get_random_name(add_random_digit=True, digit_count=5)
            # Create trigger functions
            trigger_functions = []
            for trigger in self._triggers:
                trigger_copy = trigger.copy()
                trigger_copy._set_execution_id(execution_id)
                trigger_function = trigger_copy.to_function(
                    is_async=True, raise_error=False, show_done_info=False
                )
                trigger_functions.append(
                    asyncio.create_task(trigger_function(*args, **task_kwargs))
                )
            self.print_out_dark("Waiting for next trigger")
            # Mark task as done since trigger has been defined.
            if is_first_time:
                await self._mark_done()
                is_first_time = False
            # Wait for the first task to complete
            _, pending = await asyncio.wait(
                trigger_functions, return_when=asyncio.FIRST_COMPLETED
            )
            # Cancel the remaining tasks
            for process in pending:
                try:
                    process.cancel()
                except Exception as e:
                    self.print_err(e)
            # Run the task
            task_copy = self._task.copy()
            task_copy._set_execution_id(execution_id)
            fn = task_copy.to_function(
                is_async=True, raise_error=False, show_done_info=False
            )
            self.print_out_dark(f"Add execution to the queue: {execution_id}")
            self._run_configs.append(
                RunConfig(
                    fn=fn, args=args, kwargs=task_kwargs, execution_id=execution_id
                )
            )

    async def __run_from_queue(self):
        while True:
            if len(self._run_configs) == 0:
                await asyncio.sleep(0.1)
                continue
            if self._single_execution:
                # Drain the queue, leave only the latest task
                while len(self._run_configs) > 1:
                    run_config = self._run_configs.pop(0)
                    self.print_out_dark(f"Skipping {run_config.execution_id}")
                    self.clear_xcom(execution_id=run_config.execution_id)
            # Run task
            run_config = self._run_configs.pop(0)
            self.print_out_dark(f"Executing {run_config.execution_id}")
            self.print_out_dark(f"{len(self._run_configs)} tasks left")
            await run_config.run()
            self.clear_xcom(execution_id=run_config.execution_id)
            self._play_bell()
