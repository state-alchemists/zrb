import asyncio
import copy
import os
import shutil
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional, Union

from zrb.advertisement import advertisements
from zrb.config.config import SHOW_ADVERTISEMENT, TMP_DIR
from zrb.helper.accessories.name import get_random_name
from zrb.helper.advertisement import get_advertisement
from zrb.helper.callable import run_async
from zrb.helper.map.conversion import to_str as map_to_str
from zrb.helper.string.conversion import to_variable_name
from zrb.helper.string.modification import double_quote
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
from zrb.task.base_task.component.base_task_model import BaseTaskModel
from zrb.task.base_task.component.renderer import Renderer
from zrb.task.base_task.component.trackers import AttemptTracker, FinishTracker
from zrb.task.looper import looper
from zrb.task.parallel import AnyParallel
from zrb.task_env.env import Env, PrivateEnv
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput


@typechecked
class BaseTask(FinishTracker, AttemptTracker, Renderer, BaseTaskModel, AnyTask):
    """
    Base class for all Tasks.
    Every Task definition should be extended from this class.
    """

    __running_tasks: list[AnyTask] = []

    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        description: str = "",
        inputs: list[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        upstreams: Iterable[AnyTask] = [],
        fallbacks: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0.05,
        run: Optional[Callable[..., Any]] = None,
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
    ):
        # init properties
        retry_interval = retry_interval if retry_interval >= 0 else 0
        checking_interval = checking_interval if checking_interval > 0 else 0
        retry = retry if retry >= 0 else 0
        # init parent classes
        FinishTracker.__init__(self, checking_interval=checking_interval)
        Renderer.__init__(self)
        AttemptTracker.__init__(self, retry=retry)
        BaseTaskModel.__init__(
            self,
            name=name,
            group=group,
            description=description,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            retry=retry,
            retry_interval=retry_interval,
            upstreams=upstreams,
            fallbacks=fallbacks,
            checkers=checkers,
            checking_interval=checking_interval,
            run=run,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
        )
        # init private flags
        self.__is_keyval_set = False
        self.__is_check_triggered: bool = False
        self.__is_ready: bool = False
        self.__is_execution_triggered: bool = False
        self.__is_execution_started: bool = False

    def __rshift__(
        self, operand: Union[AnyParallel, AnyTask]
    ) -> Union[AnyParallel, AnyTask]:
        if isinstance(operand, AnyTask):
            operand.add_upstream(self)
            return operand
        if isinstance(operand, AnyParallel):
            other_tasks: list[AnyTask] = operand.get_tasks()
            for other_task in other_tasks:
                other_task.add_upstream(self)
            return operand

    def __get_xcom_dir(self, execution_id: Optional[str] = None) -> str:
        if execution_id is None:
            execution_id = self.get_execution_id()
        return os.path.join(TMP_DIR, f"xcom.{execution_id}")

    def __ensure_xcom_dir_exists(self, execution_id: Optional[str] = None):
        xcom_dir = self.__get_xcom_dir(execution_id=execution_id)
        os.makedirs(xcom_dir, exist_ok=True)

    def set_task_xcom(self, key: str, value: Any):
        return self.set_xcom(key=".".join([self.get_name(), key]), value=value)

    def set_xcom(self, key: str, value: Any):
        self.__ensure_xcom_dir_exists()
        xcom_dir = self.__get_xcom_dir()
        xcom_file = os.path.join(xcom_dir, key)
        with open(xcom_file, "w") as f:
            f.write(f"{value}")

    def get_xcom(self, key: str) -> str:
        self.__ensure_xcom_dir_exists()
        xcom_dir = self.__get_xcom_dir()
        xcom_file = os.path.join(xcom_dir, key)
        with open(xcom_file, "r") as f:
            return f.read()

    def clear_xcom(self, execution_id: str = ""):
        xcom_dir = self.__get_xcom_dir(execution_id=execution_id)
        if os.path.isdir(xcom_dir):
            shutil.rmtree(xcom_dir)

    def copy(self) -> AnyTask:
        return copy.deepcopy(self)

    def __get_async_function(
        self,
        env_prefix: str = "",
        raise_error: bool = True,
        show_done_info: bool = True,
        should_clear_xcom: bool = False,
        should_stop_looper: bool = False,
    ) -> Callable[..., Any]:
        async def async_function(*args: Any, **kwargs: Any) -> Any:
            self.log_info("Copy task")
            self_cp: AnyTask = self.copy()
            result = await self_cp._run_and_check_all(
                env_prefix=env_prefix,
                raise_error=raise_error,
                args=args,
                kwargs=kwargs,
                show_done_info=show_done_info,
            )
            if should_stop_looper:
                looper.stop()
            if should_clear_xcom:
                self_cp.clear_xcom()
            return result

        return async_function

    def __to_sync_function(
        self, async_function: Callable[..., Any]
    ) -> Callable[..., Any]:
        def sync_function(*args: Any, **kwargs: Any) -> Any:
            try:
                return asyncio.run(async_function(*args, **kwargs))
            except RuntimeError as e:
                if "event loop is closed" not in str(e).lower():
                    raise e
            except asyncio.CancelledError:
                self.print_out_dark("Task is cancelled")

        return sync_function

    def to_function(
        self,
        env_prefix: str = "",
        raise_error: bool = True,
        is_async: bool = False,
        show_done_info: bool = True,
        should_clear_xcom: bool = False,
        should_stop_looper: bool = False,
    ) -> Callable[..., Any]:
        async_function = self.__get_async_function(
            env_prefix=env_prefix,
            raise_error=raise_error,
            show_done_info=show_done_info,
            should_clear_xcom=should_clear_xcom,
            should_stop_looper=should_stop_looper,
        )
        if is_async:
            return async_function
        return self.__to_sync_function(async_function)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if self._run_function is not None:
            return await run_async(self._run_function, *args, **kwargs)
        return None

    async def on_triggered(self):
        self.log_info("State: triggered")
        execution_id = self.get_execution_id()
        self.log_info(f"Execution id: {execution_id}")
        if self._on_triggered is not None:
            await run_async(self._on_triggered, self)

    async def on_waiting(self):
        self.log_info("State: waiting")
        if self._on_waiting is not None:
            await run_async(self._on_waiting, self)

    async def on_skipped(self):
        self.log_info("State: skipped")
        if self._on_skipped is not None:
            await run_async(self._on_skipped, self)

    async def on_started(self):
        self.log_info("State: started")
        if self._on_started is not None:
            await run_async(self._on_started, self)

    async def on_ready(self):
        self.log_info("State: ready")
        if self._on_ready is not None:
            await run_async(self._on_ready, self)

    async def on_failed(self, is_last_attempt: bool, exception: Exception):
        failed_state_message = "State failed"
        if is_last_attempt:
            failed_state_message = "State failed (last attempt)"
        self.log_info(failed_state_message)
        if self._on_failed is not None:
            await run_async(self._on_failed, self, is_last_attempt, exception)

    async def on_retry(self):
        self.log_info("State: retry")
        if self._on_retry is not None:
            await run_async(self._on_retry, self)

    async def check(self) -> bool:
        return await run_async(self._is_done)

    def inject_envs(self):
        super().inject_envs()
        input_map = self.get_input_map()
        for task_input in self._get_combined_inputs():
            input_key = to_variable_name(task_input.get_name())
            input_value = input_map.get(input_key)
            env_name = "_INPUT_" + input_key.upper()
            should_render = task_input.should_render()
            self.add_env(
                PrivateEnv(
                    name=env_name, default=str(input_value), should_render=should_render
                )
            )

    async def _run_and_check_all(
        self,
        env_prefix: str,
        raise_error: bool,
        args: Iterable[Any],
        kwargs: Mapping[str, Any],
        show_done_info: bool = True,
    ):
        try:
            self._start_timer()
            if self.get_execution_id() == "":
                self._set_execution_id(
                    get_random_name(add_random_digit=True, digit_count=5)
                )
                self._propagate_execution_id()
            self.log_info("Set input and env map")
            await self._set_keyval(kwargs=kwargs, env_prefix=env_prefix)
            self.log_info("Set run kwargs")
            new_kwargs = self.get_input_map()
            # make sure args and kwargs['_args'] are the same
            self.log_info("Set run args")
            new_args = list(args)
            if len(args) == 0 and "_args" in kwargs:
                new_args = kwargs["_args"]
            self._set_args(new_args)
            self._set_kwargs(new_kwargs)
            # run the task
            coroutines = [
                asyncio.create_task(self._loop_check(show_done_info=show_done_info)),
                asyncio.create_task(
                    self._run_all(*new_args, _args=new_args, _task=self, **new_kwargs)
                ),
            ]
            results = await asyncio.gather(*coroutines)
            result = results[-1]
            self._print_result(result)
            return result
        except Exception as e:
            self.log_error(f"{e}")
            if raise_error:
                raise e
        finally:
            if show_done_info:
                self._show_env_prefix()
                self._show_run_command()
                self._play_bell()

    async def _loop_check(self, show_done_info: bool = False) -> bool:
        self.log_info("Start readiness checking")
        while not await self._cached_check():
            self.log_debug("Task is not ready")
            await asyncio.sleep(self._checking_interval)
        self._end_timer()
        if show_done_info:
            if SHOW_ADVERTISEMENT:
                selected_advertisement = get_advertisement(advertisements)
                selected_advertisement.show()
            self._show_done_info()
        await self.on_ready()
        return True

    async def _cached_check(self) -> bool:
        if self.__is_check_triggered:
            self.log_debug("Waiting readiness flag to be set")
            while not self.__is_ready:
                await asyncio.sleep(self._checking_interval)
            return True
        self.__is_check_triggered = True
        check_result = await self._check()
        if check_result:
            self.__is_ready = True
            self.log_debug("Set readiness flag to True")
        return check_result

    async def _check(self) -> bool:
        """
        Check current task readiness.
        - If self.checkers is defined,
          this will return True once every self.checkers is completed
        - Otherwise, this will return check method's return value.
        """
        if len(self._get_checkers()) == 0:
            return await run_async(self.check)
        self.log_debug("Waiting execution to be started")
        while not self.__is_execution_started:
            # Don't start checking before the execution itself has been started
            await asyncio.sleep(self._checking_interval / 2.0)
        check_coroutines: Iterable[asyncio.Task] = []
        for checker_task in self._get_checkers():
            checker_task._set_execution_id(self.get_execution_id())
            check_coroutines.append(asyncio.create_task(checker_task._run_all()))
        await asyncio.gather(*check_coroutines)
        return True

    async def _run_all(self, *args: Any, **kwargs: Any) -> Any:
        await self._mark_awaited()
        coroutines: Iterable[asyncio.Task] = []
        # Add upstream tasks to processes
        self._lock_upstreams()
        for upstream_task in self._get_upstreams():
            upstream_task._set_execution_id(self.get_execution_id())
            coroutines.append(asyncio.create_task(upstream_task._run_all(**kwargs)))
        # Add current task to processes
        coroutines.append(self._cached_run(*args, **kwargs))
        # Wait everything to complete
        results = await asyncio.gather(*coroutines)
        if self._return_upstream_result:
            return results[0:-1]
        return results[-1]

    async def _cached_run(self, *args: Any, **kwargs: Any) -> Any:
        if self.__is_execution_triggered:
            self.log_debug("Task has been triggered")
            return
        await self.on_triggered()
        self.__is_execution_triggered = True
        await self.on_waiting()
        await self.__check_upstreams()
        # mark execution as started, so that checkers can start checking
        self.__is_execution_started = True
        local_kwargs = dict(kwargs)
        local_kwargs["_task"] = self
        if not await self._check_should_execute(*args, **local_kwargs):
            await self.on_skipped()
            await self._mark_done()
            return None
        # start running task
        result: Any = None
        is_failed: bool = False
        while self._should_attempt():
            try:
                self.log_debug(
                    f"Started with args: {args} and kwargs: {local_kwargs}"
                )  # noqa
                await self.on_started()
                self.__running_tasks.append(self)
                result = await run_async(self.run, *args, **local_kwargs)
                self.__running_tasks.remove(self)
                break
            except Exception as e:
                attempt = self._get_attempt()
                self.log_error(f"Encounter error on attempt {attempt}")
                if self._is_last_attempt():
                    is_failed = True
                    raise e
                self.__running_tasks.remove(self)
                await self.on_failed(is_last_attempt=False, exception=e)
                self._increase_attempt()
                await asyncio.sleep(self._retry_interval)
                await self.on_retry()
            finally:
                if is_failed:
                    running_tasks = self.__running_tasks
                    self.__running_tasks = []
                    await self.__trigger_failure(running_tasks)
                    await self.__trigger_fallbacks(running_tasks, kwargs)
        self.set_xcom(self.get_name(), f"{result}")
        await self._mark_done()
        return result

    async def __check_upstreams(self):
        coroutines: Iterable[asyncio.Task] = []
        self._lock_upstreams()
        for upstream_task in self._get_upstreams():
            coroutines.append(asyncio.create_task(upstream_task._loop_check()))
        # wait all upstream checkers to complete
        await asyncio.gather(*coroutines)

    async def __trigger_failure(self, tasks: list[AnyTask]):
        coroutines = [
            task.on_failed(is_last_attempt=True, exception=Exception("canceled"))
            for task in tasks
        ]
        await asyncio.gather(*coroutines)

    async def __trigger_fallbacks(
        self, tasks: list[AnyTask], kwargs: Mapping[str, Any]
    ):
        coroutines: Iterable[asyncio.Task] = []
        for fallback in self.__get_all_fallbacks(tasks):
            fallback._set_execution_id(self.get_execution_id())
            coroutines.append(asyncio.create_task(fallback._run_all(**kwargs)))
        await asyncio.gather(*coroutines)

    def __get_all_fallbacks(self, tasks: list[AnyTask]) -> list[AnyTask]:
        all_fallbacks: list[AnyTask] = []
        for task in tasks:
            task._lock_fallbacks()
            for fallback in task._get_fallbacks():
                if fallback not in all_fallbacks:
                    all_fallbacks.append(fallback)
        return all_fallbacks

    async def _check_should_execute(self, *args: Any, **kwargs: Any) -> bool:
        if callable(self._should_execute):
            return await run_async(self._should_execute, *args, **kwargs)
        return self.render_bool(self._should_execute)

    async def _set_keyval(self, kwargs: Mapping[str, Any], env_prefix: str):
        # if input is not in input_map, add default values
        for task_input in self._get_combined_inputs():
            key = to_variable_name(task_input.get_name())
            if key in kwargs:
                continue
            kwargs[key] = task_input.get_default()
        # set current task local keyval
        await self._set_local_keyval(kwargs=kwargs, env_prefix=env_prefix)
        # get new_kwargs for upstream and checkers
        new_kwargs = {key: kwargs[key] for key in kwargs}
        new_kwargs.update(self.get_input_map())
        upstream_coroutines = []
        # set upstreams keyval
        self._lock_upstreams()
        for upstream_task in self._get_upstreams():
            upstream_coroutines.append(
                asyncio.create_task(
                    upstream_task._set_keyval(kwargs=new_kwargs, env_prefix=env_prefix)
                )
            )
        # set checker keyval
        self._lock_checkers()
        checker_coroutines = []
        for checker_task in self._get_checkers():
            checker_coroutines.append(
                asyncio.create_task(
                    checker_task._set_keyval(kwargs=new_kwargs, env_prefix=env_prefix)
                )
            )
        # wait for checker and upstreams
        coroutines = checker_coroutines + upstream_coroutines
        await asyncio.gather(*coroutines)

    async def _set_local_keyval(self, kwargs: Mapping[str, Any], env_prefix: str = ""):
        if self.__is_keyval_set:
            return True
        self.__is_keyval_set = True
        # set task for rendering
        self._set_task(self)
        # Set input_map for rendering
        self.log_info("Set input map")
        for task_input in self._get_combined_inputs():
            input_name = to_variable_name(task_input.get_name())
            input_value = kwargs.get(input_name, task_input.get_default())
            if task_input.should_render():
                input_value = self.render_any(input_value)
            self._set_input_map(input_name, input_value)
        self.log_debug(
            "Input map:\n" + map_to_str(self.get_input_map(), item_prefix="  ")
        )
        self.log_info("Merging task envs, task env files, and native envs")
        # Set env_map for rendering
        for env_name, env in self._get_combined_env().items():
            env_value = env.get(env_prefix)
            if env.should_render():
                env_value = self.render_any(env_value)
            self._set_env_map(env_name, env_value)
        # Add some default Env Map
        execution_id = self.get_execution_id()
        self._set_env_map("_ZRB_EXECUTION_ID", execution_id)
        xcom_dir = self.__get_xcom_dir()
        self._set_env_map("_ZRB_XCOM_DIR", xcom_dir)
        self.log_debug("Env map:\n" + map_to_str(self.get_env_map(), item_prefix="  "))

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        full_cli_name = double_quote(self._get_full_cli_name())
        return f"<{cls_name} {full_cli_name}>"
