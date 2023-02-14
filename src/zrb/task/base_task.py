from typing import (
    Any, Callable, Iterable, Mapping, Optional, Tuple, TypeVar
)
from typeguard import typechecked
from .base_model import TaskModel
from ..task_input.base_input import BaseInput
from ..task_env.env import Env
from ..task_group.group import Group
from ..helper.list.append_unique import append_unique
from ..helper.string.conversion import to_variable_name


import asyncio
import copy

TTask = TypeVar('TTask', bound='BaseTask')


@typechecked
class BaseTask(TaskModel):
    '''
    Base class for all tasks.
    Every task definition should be extended from this class.
    '''

    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        inputs: Iterable[BaseInput] = [],
        envs: Iterable[Env] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        upstreams: Iterable[TTask] = [],
        checkers: Iterable[TTask] = [],
        checking_interval: float = 0.1,
        retry: int = 2,
        retry_interval: float = 1,
        run: Optional[Callable[..., Any]] = None
    ):
        TaskModel.__init__(
            self,
            name=name,
            group=group,
            envs=envs,
            icon=icon,
            color=color,
            retry=retry
        )
        retry_interval = self.ensure_non_negative(
            retry_interval, 'Find negative retry_interval'
        )
        checking_interval = self.ensure_non_negative(
            checking_interval, 'Find negative checking_interval'
        )
        self.inputs = inputs
        self.description = description
        self.retry_interval = retry_interval
        self.upstreams = upstreams
        self.checkers = checkers
        self.checking_interval = checking_interval
        self._is_checked: bool = False
        self._is_executed: bool = False
        self._runner: Optional[Callable[..., Any]] = run

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        '''
        Do task execution
        Please override this method.
        '''
        if self._runner is not None:
            return self._runner(*args, **kwargs)
        return True

    async def check(self) -> bool:
        '''
        Return true when task is considered completed.
        By default, this will wait the task execution to be completed.
        You can override this method.
        '''
        return self.is_done()

    def get_all_inputs(self) -> Iterable[BaseInput]:
        ''''
        Getting all inputs of this task and all its upstream, non-duplicated.
        '''
        inputs: Iterable[BaseInput] = []
        for upstream in self.upstreams:
            upstream_inputs = upstream.get_all_inputs()
            append_unique(inputs, *upstream_inputs)
        append_unique(inputs, *self.inputs)
        return inputs

    def get_description(self) -> str:
        if self.description != '':
            return self.description
        return self.name

    def create_main_loop(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., Any]:
        def main_loop(*args: Any, **kwargs: Any) -> Any:
            '''
            Task main loop.
            '''
            self.start_timer()
            self_cp, args, kwargs = self._get_main_loop_variables(
                env_prefix=env_prefix, args=args, kwargs=kwargs
            )

            async def run_and_check_all_async() -> Any:
                # initiate args
                processes = [
                    asyncio.create_task(self_cp._loop_check(True)),
                    asyncio.create_task(self_cp._run_all(*args, **kwargs))
                ]
                results = await asyncio.gather(*processes)
                return results[-1]
            try:
                result = asyncio.run(run_and_check_all_async())
                self._print_result(result)
                return result
            except Exception as exception:
                self_cp.log_error(f'{exception}')
                if raise_error:
                    raise
            finally:
                self_cp.play_bell()
        return main_loop

    def _get_main_loop_variables(
        self, env_prefix: str, args: Iterable[Any], kwargs: Mapping[str, Any]
    ) -> Tuple[TTask, Iterable[str], Mapping[str, Any]]:
        self_cp = copy.deepcopy(self)
        kwargs = {
            self._get_normalized_input_key(key): value
            for key, value in kwargs.items()
        }
        # ensure args and kwargs[_args] has the same value
        if len(args) == 0 and '_args' in kwargs:
            args = kwargs['_args']
        kwargs['_args'] = args
        # ensure kwargs are complete
        for task_input in self.inputs:
            kwarg_key = to_variable_name(task_input.name)
            if kwarg_key not in kwargs:
                kwargs[kwarg_key] = task_input.default
        # inject kwargs[_task]
        kwargs['_task'] = self_cp
        self_cp._set_keyval(input_map=kwargs, env_prefix=env_prefix)
        return self_cp, args, kwargs

    def _print_result(self, result: Any):
        '''
        Print result to stdout so that it can be processed further.
        e.g.: echo $(zrb show principle solid) > solid-principle.txt

        You need to override this method
        if you want to show the result differently.
        '''
        if result is None:
            return
        print(result)

    async def _loop_check(self, show_celebration: bool = False) -> bool:
        while not await self._cached_check():
            self.log_debug('Task is not ready')
            await asyncio.sleep(self.checking_interval)
        self.end_timer()
        self.log_info('Task is ready')
        if show_celebration:
            self.show_celebration()
        return True

    async def _cached_check(self) -> bool:
        if self._is_checked:
            self.log_debug('Skip checking, because checking flag has been set')
            return True
        check_result = await self._check()
        if check_result:
            self._is_checked = True
            self.log_debug('Set checking flag to True')
        return check_result

    async def _check(self) -> bool:
        '''
        Check current task readiness.
        - If self.checkers is defined,
          this will return True once every self.checkers is completed
        - Otherwise, this will return check method's return value.
        '''
        if len(self.checkers) == 0:
            return await self.check()
        check_processes: Iterable[asyncio.Task] = []
        for checker_task in self.checkers:
            check_processes.append(asyncio.create_task(checker_task.run()))
        await asyncio.gather(*check_processes)
        return True

    async def _run_all(self, *args: Any, **kwargs: Any) -> Any:
        processes: Iterable[asyncio.Task] = []
        # Add upstream tasks to processes
        for upstream_task in self.upstreams:
            processes.append(asyncio.create_task(
                upstream_task._run_all(**kwargs)
            ))
        # Add current task to processes
        processes.append(self._cached_run(*args, **kwargs))
        # Wait everything to complete
        results = await asyncio.gather(*processes)
        return results[-1]

    async def _cached_run(self, *args: Any, **kwargs: Any) -> Any:
        if self._is_executed:
            self.log_debug('Skip running, because execution flag has been set')
            return
        self.log_debug('Set execution flag to True')
        self._is_executed = True
        self.log_debug('Start running')
        # get upstream checker
        upstream_check_processes: Iterable[asyncio.Task] = []
        for upstream_task in self.upstreams:
            upstream_check_processes.append(asyncio.create_task(
                upstream_task._loop_check()
            ))
        # wait all upstream checkers to complete
        await asyncio.gather(*upstream_check_processes)
        # start running task
        result: Any
        while self.should_attempt():
            try:
                self.log_debug(
                    f'Invoke run with args: {args} and kwargs: {kwargs}'
                )
                result = await self.run(*args, **kwargs)
                break
            except Exception:
                if self.is_last_attempt():
                    raise
                attempt = self.get_attempt()
                self.log_error(f'Encounter error on attempt {attempt}')
                self.increase_attempt()
                await asyncio.sleep(self.retry_interval)
        self.mark_as_done()
        return result

    def _set_keyval(self, input_map: Mapping[str, Any], env_prefix: str):
        self._set_local_keyval(input_map=input_map, env_prefix=env_prefix)
        for upstream_task in self.upstreams:
            upstream_task._set_keyval(
                input_map=input_map, env_prefix=env_prefix
            )
        local_env_map = self.get_env_map()
        for checker_task in self.checkers:
            checker_task._set_keyval(
                input_map=input_map, env_prefix=env_prefix
            )
            # Checker task should be able to read local env
            checker_task._inject_env_map(local_env_map)
