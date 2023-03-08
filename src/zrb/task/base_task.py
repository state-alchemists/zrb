from typing import (
    Any, Callable, Iterable, List, Mapping, Optional, Tuple, TypeVar, Union
)
from typeguard import typechecked
from .base_model import TaskModel
from ..advertisement import advertisements
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_group.group import Group
from ..task_input.base_input import BaseInput
from ..helper.accessories.color import colored
from ..helper.advertisement import get_advertisement
from ..helper.list.append_unique import append_unique
from ..helper.string.double_quote import double_quote

import asyncio
import inspect
import copy
import sys

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
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        upstreams: Iterable[TTask] = [],
        checkers: Iterable[TTask] = [],
        checking_interval: float = 0,
        retry: int = 2,
        retry_interval: float = 1,
        run: Optional[Callable[..., Any]] = None,
        skip_execution: Union[bool, str] = False
    ):
        TaskModel.__init__(
            self,
            name=name,
            group=group,
            envs=envs,
            env_files=env_files,
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
        if checking_interval == 0:
            checking_interval = 0.05 if len(checkers) == 0 else 0.1
        self.inputs = inputs
        self.description = description
        self.retry_interval = retry_interval
        self.upstreams = upstreams
        self.checkers = checkers
        self.checking_interval = checking_interval
        self.skip_execution = skip_execution
        self._is_checked: bool = False
        self._is_executed: bool = False
        self._run_function: Optional[Callable[..., Any]] = run

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        '''
        Do task execution
        Please override this method.
        '''
        if self._run_function is not None:
            if inspect.iscoroutinefunction(self._run_function):
                return await self._run_function(*args, **kwargs)
            return self._run_function(*args, **kwargs)
        return True

    async def check(self) -> bool:
        '''
        Return true when task is considered completed.
        By default, this will wait the task execution to be completed.
        You can override this method.
        '''
        return await self.is_done()

    def get_all_inputs(self) -> Iterable[BaseInput]:
        ''''
        Getting all inputs of this task and all its upstream, non-duplicated.
        '''
        if self._all_inputs is not None:
            return self._all_inputs
        inputs: Iterable[BaseInput] = []
        for upstream in self.upstreams:
            upstream_inputs = upstream.get_all_inputs()
            append_unique(inputs, *upstream_inputs)
        append_unique(inputs, *self.inputs)
        self._all_inputs = inputs
        return inputs

    def get_description(self) -> str:
        if self.description != '':
            return self.description
        return self.name

    def create_main_loop(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., Any]:
        def main_loop(*args: Any, **kwargs: Any) -> Any:
            self.start_timer()
            self_cp, args, kwargs = asyncio.run(self._get_main_loop_variables(
                env_prefix=env_prefix, args=args, kwargs=kwargs
            ))
            try:
                result = asyncio.run(
                    self_cp._run_and_check_all(*args, **kwargs)
                )
                self._print_result(result)
                return result
            except Exception as exception:
                self_cp.log_critical(f'{exception}')
                if raise_error:
                    raise
            finally:
                self_cp.play_bell()
        return main_loop

    async def _run_and_check_all(self, *args: Any, **kwargs: Any):
        processes = [
            asyncio.create_task(self._loop_check(True)),
            asyncio.create_task(self._run_all(*args, **kwargs))
        ]
        results = await asyncio.gather(*processes)
        return results[-1]

    async def _get_main_loop_variables(
        self, env_prefix: str, args: Iterable[Any], kwargs: Mapping[str, Any]
    ) -> Tuple[TTask, Iterable[str], Mapping[str, Any]]:
        self_cp = copy.deepcopy(self)
        await self_cp._set_keyval(kwargs=kwargs, env_prefix=env_prefix)
        # init new_kwargs
        new_kwargs = copy.deepcopy(self_cp._input_map)
        # init new_args, make sure it has the same value as new_kwargs['_args']
        new_args = copy.deepcopy(args)
        if len(args) == 0 and '_args' in kwargs:
            new_args = kwargs['_args']
        new_kwargs['_args'] = new_args
        # inject new_kwargs['_task']
        new_kwargs['_task'] = self_cp
        return self_cp, new_args, new_kwargs

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

    async def _loop_check(self, show_info: bool = False) -> bool:
        while not await self._cached_check():
            self.log_debug('Task is not ready')
            await asyncio.sleep(self.checking_interval)
        self.end_timer()
        self.log_info('Task is ready')
        if show_info:
            get_advertisement(advertisements).show()
            self.show_done_info()
            self.show_run_command()
        return True

    def show_run_command(self):
        params: List[str] = []
        for task_input in self.inputs:
            key = task_input.name
            map_key = self._get_normalized_input_key(key)
            value = str(self._input_map.get(map_key))
            quoted_value = double_quote(value)
            params.append(f'--{key} {quoted_value}')
        run_cmd = self._get_complete_name()
        run_cmd_with_param = run_cmd
        if len(params) > 0:
            param_str = ' '.join(params)
            run_cmd_with_param += ' ' + param_str
        colored_run_cmd = colored(f'{run_cmd_with_param}', color='yellow')
        colored_label = colored('Run again: ', attrs=['dark'])
        print(colored(f'{colored_label}{colored_run_cmd}'), file=sys.stderr)

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
        await self.mark_start()
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
            self.log_debug('Skip execution because execution flag is True')
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
        if self.render_bool(self.skip_execution):
            self.log_info(
                f'Skip execution because config: {self.skip_execution}'
            )
            await self.mark_as_done()
            return None
        # start running task
        result: Any
        local_kwargs = dict(kwargs)
        local_kwargs['_task'] = self
        while self.should_attempt():
            try:
                self.log_debug(
                    f'Invoke run with args: {args} and kwargs: {local_kwargs}'
                )
                result = await self.run(*args, **local_kwargs)
                break
            except Exception:
                if self.is_last_attempt():
                    raise
                attempt = self.get_attempt()
                self.log_error(f'Encounter error on attempt {attempt}')
                self.increase_attempt()
                await asyncio.sleep(self.retry_interval)
        await self.mark_as_done()
        return result

    async def _set_keyval(self, kwargs: Mapping[str, Any], env_prefix: str):
        # if input is not in input_map, add default values
        for task_input in self.get_all_inputs():
            key = self._get_normalized_input_key(task_input.name)
            if key in kwargs:
                continue
            kwargs[key] = task_input.default
        # set current task local keyval
        await self._set_local_keyval(kwargs=kwargs, env_prefix=env_prefix)
        # get new_kwargs for upstream and checkers
        new_kwargs = copy.deepcopy(kwargs)
        new_kwargs.update(self._input_map)
        upstream_processes = []
        # set uplstreams keyval
        for upstream_task in self.upstreams:
            upstream_processes.append(asyncio.create_task(
                upstream_task._set_keyval(
                    kwargs=new_kwargs, env_prefix=env_prefix
                )
            ))
        await asyncio.gather(*upstream_processes)
        # set checker keyval
        local_env_map = self.get_env_map()
        checker_processes = []
        for checker_task in self.checkers:
            checker_task.inputs += self.inputs
            checker_task._inject_env_map(local_env_map)
            checker_processes.append(asyncio.create_task(
                checker_task._set_keyval(
                    kwargs=new_kwargs, env_prefix=env_prefix
                )
            ))
        await asyncio.gather(*checker_processes)
