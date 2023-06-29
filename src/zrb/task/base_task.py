from typing import (
    Any, Callable, Iterable, List, Mapping, Optional, Union
)
from typeguard import typechecked
from .any_task import AnyTask
from .base_task_composite import (
    AttemptTracker, FinishTracker, Renderer, TaskModelWithPrinterAndTracker
)
from ..advertisement import advertisements
from ..task_group.group import Group
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_input.base_input import BaseInput
from ..task_input._constant import RESERVED_INPUT_NAMES
from ..helper.accessories.color import colored
from ..helper.advertisement import get_advertisement
from ..helper.list.ensure_uniqueness import ensure_uniqueness
from ..helper.list.reverse import reverse
from ..helper.string.double_quote import double_quote
from ..helper.string.conversion import to_variable_name
from ..helper.map.conversion import to_str as str_map_to_str
from ..config.config import show_advertisement

import asyncio
import copy
import inspect
import os
import sys

MULTILINE_INDENT = ' ' * 8


@typechecked
class BaseTask(
    FinishTracker, AttemptTracker, Renderer, TaskModelWithPrinterAndTracker,
    AnyTask
):
    '''
    Base class for all tasks.
    Every task definition should be extended from this class.
    '''
    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        description: str = '',
        inputs: List[BaseInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        retry: int = 2,
        retry_interval: float = 1,
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: float = 0,
        run: Optional[Callable[..., Any]] = None,
        skip_execution: Union[bool, str, Callable[..., bool]] = False
    ):
        # init properties
        retry_interval = retry_interval if retry_interval >= 0 else 0
        checking_interval = checking_interval if checking_interval > 0 else 0.1
        retry = retry if retry >= 0 else 0
        # init parent classes
        FinishTracker.__init__(self)
        Renderer.__init__(self)
        AttemptTracker.__init__(self, retry=retry)
        TaskModelWithPrinterAndTracker.__init__(
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
            checkers=checkers,
            checking_interval=checking_interval,
            run=run,
            skip_execution=skip_execution,
        )
        # init private properties
        self._is_keyval_set = False  # Flag
        self._all_inputs: Optional[List[BaseInput]] = None
        self._is_check_triggered: bool = False
        self._is_ready: bool = False
        self._is_execution_triggered: bool = False
        self._is_execution_started: bool = False
        self._args: List[Any] = []
        self._kwargs: Mapping[str, Any] = {}
        self._allow_add_upstream: bool = True

    def get_all_inputs(self) -> Iterable[BaseInput]:
        ''''
        Getting all inputs of this task and all its upstream, non-duplicated.
        '''
        if self._all_inputs is not None:
            return self._all_inputs
        inputs: Iterable[BaseInput] = []
        self._allow_add_upstream = False
        for upstream in self._upstreams:
            upstream_inputs = upstream.get_all_inputs()
            inputs += upstream_inputs
        inputs += self._inputs
        self._all_inputs = ensure_uniqueness(
            inputs, lambda x, y: x.name == y.name
        )
        return inputs

    def to_function(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., Any]:
        self.log_info('Create function')

        def function(*args: Any, **kwargs: Any) -> Any:
            self.log_info('Copy task')
            self_cp = copy.deepcopy(self)
            return asyncio.run(self_cp._run_and_check_all(
                env_prefix=env_prefix,
                raise_error=raise_error,
                args=args,
                kwargs=kwargs
            ))
        return function

    def add_upstreams(self, *upstreams: AnyTask):
        if not self._allow_add_upstream:
            raise Exception(f'Cannot add upstreams on `{self._name}`')
        self._upstreams += upstreams

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
        return await self._is_done()

    def _show_done_info(self):
        complete_name = self._get_complete_name()
        elapsed_time = self._get_elapsed_time()
        message = '\n'.join([
            f'{complete_name} completed in {elapsed_time} seconds',
        ])
        self.print_out_dark(message)
        self._play_bell()

    def _inject_env_map(
        self, env_map: Mapping[str, str], override: bool = False
    ):
        for key, val in env_map.items():
            if override or key not in self._env_map:
                self._env_map[key] = val

    def _get_multiline_repr(self, text: str) -> str:
        lines_repr: Iterable[str] = []
        lines = text.split('\n')
        if len(lines) == 1:
            return lines[0]
        for index, line in enumerate(lines):
            line_number_repr = str(index + 1).rjust(4, '0')
            lines_repr.append(f'{MULTILINE_INDENT}{line_number_repr} | {line}')
        return '\n' + '\n'.join(lines_repr)

    async def _set_local_keyval(
        self,
        kwargs: Mapping[str, Any],
        env_prefix: str = ''
    ):
        if self._is_keyval_set:
            return True
        self._is_keyval_set = True
        # Add self.inputs to input_map
        self.log_info('Set input map')
        for task_input in self.get_all_inputs():
            map_key = self._get_normalized_input_key(task_input.name)
            self._input_map[map_key] = self.render_any(
                kwargs.get(map_key, task_input.default)
            )
        self.log_debug(
            f'Input map:\n{str_map_to_str(self._input_map, item_prefix="  ")}'
        )
        # Construct envs based on self.env_files and self.envs,
        # - self.env_files should have lower priority then self.envs
        # - First self.envs/self.env_files should be overriden by the next
        self.log_info('Merging task envs, task env files, and native envs')
        envs: List[Env] = self._deduplicate_env(self._envs)
        for env_file in reverse(self._env_files):
            envs += env_file.get_envs()
        for env_name in os.environ:
            envs.append(Env(name=env_name, os_name=env_name, renderable=False))
        envs = ensure_uniqueness(envs, self._compare_env_name)
        # Add envs to env_map
        self.log_info('Set env map')
        for task_env in envs:
            env_name = task_env.name
            if env_name in self._env_map:
                continue
            env_value = task_env.get(env_prefix)
            if task_env.renderable:
                env_value = self.render_any(env_value)
            self._env_map[env_name] = env_value
        self.log_debug(
            f'Env map:\n{str_map_to_str(self._env_map, item_prefix="  ")}'
        )

    def _deduplicate_env(self, envs: Iterable[Env]) -> List[Env]:
        # If two environment with the same name exists, the second one should
        # override the first one. But the order of the declaration should not
        # be changed
        return reverse(ensure_uniqueness(
            reverse(envs), self._compare_env_name
        ))

    def _compare_env_name(self, first_env: Env, second_env: Env) -> bool:
        return first_env.name == second_env.name

    def _get_normalized_input_key(self, key: str) -> str:
        if key in RESERVED_INPUT_NAMES:
            return key
        return to_variable_name(key)

    async def _run_and_check_all(
        self,
        env_prefix: str,
        raise_error: bool,
        args: Iterable[Any],
        kwargs: Mapping[str, Any]
    ):
        try:
            self._start_timer()
            self.log_info('Set input and env map')
            await self._set_keyval(kwargs=kwargs, env_prefix=env_prefix)
            self.log_info('Set run kwargs')
            # new_kwargs is bound to self._input_map
            # Any changes on new_kwargs will affect self._input_map
            # Thus, change self._render_str/self._render_file behavior as well
            new_kwargs = self.get_input_map()
            # make sure args and kwargs['_args'] are the same
            self.log_info('Set run args')
            new_args = copy.deepcopy(args)
            if len(args) == 0 and '_args' in kwargs:
                new_args = kwargs['_args']
            new_kwargs['_args'] = new_args
            # inject self as kwargs['_task']
            new_kwargs['_task'] = self
            self._args = new_args
            self._kwargs = new_kwargs
            # run the task
            coroutines = [
                asyncio.create_task(self._loop_check(show_info=True)),
                asyncio.create_task(self._run_all(*new_args, **new_kwargs))
            ]
            results = await asyncio.gather(*coroutines)
            result = results[-1]
            self._print_result(result)
            return result
        except Exception as e:
            self.log_critical(f'{e}')
            if raise_error:
                raise
        finally:
            self._play_bell()

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
        self.log_info('Start checking')
        while not await self._cached_check():
            self.log_debug('Task is not ready')
            await asyncio.sleep(self._checking_interval)
        self._end_timer()
        self.log_info('State: ready')
        if show_info:
            if show_advertisement:
                selected_advertisement = get_advertisement(advertisements)
                selected_advertisement.show()
            self._show_done_info()
            self._show_run_command()
        return True

    def _show_run_command(self):
        params: List[str] = [double_quote(arg) for arg in self._args]
        for task_input in self.get_all_inputs():
            key = task_input.name
            kwarg_key = self._get_normalized_input_key(key)
            quoted_value = double_quote(str(self._kwargs[kwarg_key]))
            params.append(f'--{key} {quoted_value}')
        run_cmd = self._get_complete_name()
        run_cmd_with_param = run_cmd
        if len(params) > 0:
            param_str = ' '.join(params)
            run_cmd_with_param += ' ' + param_str
        colored_run_cmd = colored(f'{run_cmd_with_param}', color='yellow')
        colored_label = colored('To run again: ', attrs=['dark'])
        print(colored(f'{colored_label}{colored_run_cmd}'), file=sys.stderr)

    async def _cached_check(self) -> bool:
        if self._is_check_triggered:
            self.log_debug('Waiting checking flag to be set')
            while not self._is_ready:
                await asyncio.sleep(0.1)
            return True
        self._is_check_triggered = True
        self.log_debug('Start checking')
        check_result = await self._check()
        if check_result:
            self._is_ready = True
            self.log_debug('Set checking flag to True')
        return check_result

    async def _check(self) -> bool:
        '''
        Check current task readiness.
        - If self.checkers is defined,
          this will return True once every self.checkers is completed
        - Otherwise, this will return check method's return value.
        '''
        if len(self._checkers) == 0:
            return await self.check()
        self.log_debug('Waiting execution to be started')
        while not self._is_execution_started:
            # Don't start checking before the execution itself has been started
            await asyncio.sleep(0.1)
        check_coroutines: Iterable[asyncio.Task] = []
        for checker_task in self._checkers:
            check_coroutines.append(
                asyncio.create_task(checker_task._run_all())
            )
        await asyncio.gather(*check_coroutines)
        return True

    async def _run_all(self, *args: Any, **kwargs: Any) -> Any:
        await self._mark_awaited()
        coroutines: Iterable[asyncio.Task] = []
        # Add upstream tasks to processes
        self._allow_add_upstream = False
        for upstream_task in self._upstreams:
            coroutines.append(asyncio.create_task(
                upstream_task._run_all(**kwargs)
            ))
        # Add current task to processes
        coroutines.append(self._cached_run(*args, **kwargs))
        # Wait everything to complete
        results = await asyncio.gather(*coroutines)
        return results[-1]

    async def _cached_run(self, *args: Any, **kwargs: Any) -> Any:
        if self._is_execution_triggered:
            self.log_debug('Task has been triggered')
            return
        self.log_info('State: triggered')
        self._is_execution_triggered = True
        self.log_info('State: waiting')
        # get upstream checker
        upstream_check_processes: Iterable[asyncio.Task] = []
        self._allow_add_upstream = False
        for upstream_task in self._upstreams:
            upstream_check_processes.append(asyncio.create_task(
                upstream_task._loop_check()
            ))
        # wait all upstream checkers to complete
        await asyncio.gather(*upstream_check_processes)
        # mark execution as started, so that checkers can start checking
        self._is_execution_started = True
        local_kwargs = dict(kwargs)
        local_kwargs['_task'] = self
        if await self._check_skip_execution(*args, **local_kwargs):
            self.log_info(
                f'Skip execution because config: {self._skip_execution}'
            )
            self.log_info('State: stopped')
            await self._mark_done()
            return None
        # start running task
        result: Any
        while self._should_attempt():
            try:
                self.log_debug(
                    f'Started with args: {args} and kwargs: {local_kwargs}'
                )
                self.log_info('State: started')
                result = await self.run(*args, **local_kwargs)
                break
            except Exception:
                self.log_info('State: failed')
                if self._is_last_attempt():
                    raise
                attempt = self._get_attempt()
                self.log_error(f'Encounter error on attempt {attempt}')
                self._increase_attempt()
                await asyncio.sleep(self._retry_interval)
                self.log_info('State: retry')
        await self._mark_done()
        self.log_info('State: stopped')
        return result

    async def _check_skip_execution(self, *args: Any, **kwargs: Any) -> bool:
        if callable(self._skip_execution):
            if inspect.iscoroutinefunction(self._skip_execution):
                return await self._skip_execution(*args, **kwargs)
            return self._skip_execution(*args, **kwargs)
        return self.render_bool(self._skip_execution)

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
        upstream_coroutines = []
        # set uplstreams keyval
        self._allow_add_upstream = False
        for upstream_task in self._upstreams:
            upstream_coroutines.append(asyncio.create_task(
                upstream_task._set_keyval(
                    kwargs=new_kwargs, env_prefix=env_prefix
                )
            ))
        # set checker keyval
        local_env_map = self.get_env_map()
        checker_coroutines = []
        for checker_task in self._checkers:
            checker_task._inputs += self._inputs
            checker_task._inject_env_map(local_env_map, override=True)
            checker_coroutines.append(asyncio.create_task(
                checker_task._set_keyval(
                    kwargs=new_kwargs, env_prefix=env_prefix
                )
            ))
        # wait for checker and upstreams
        coroutines = checker_coroutines + upstream_coroutines
        await asyncio.gather(*coroutines)
