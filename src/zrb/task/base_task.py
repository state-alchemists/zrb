from typing import (
    Any, Callable, Iterable, List, Mapping, Optional, TypeVar, Union
)
from typeguard import typechecked
from ..advertisement import advertisements
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_input.base_input import BaseInput
from ..task_input._constant import RESERVED_INPUT_NAMES
from ..helper.accessories.color import (
    get_random_color, is_valid_color, colored
)
from ..helper.accessories.icon import get_random_icon
from ..helper.advertisement import get_advertisement
from ..helper.list.ensure_uniqueness import ensure_uniqueness
from ..helper.list.reverse import reverse
from ..helper.log import logger
from ..helper.render_data import DEFAULT_RENDER_DATA
from ..helper.string.double_quote import double_quote
from ..helper.string.conversion import (
    to_cmd_name, to_variable_name, to_boolean
)
from ..helper.map.conversion import to_str as str_map_to_str
from ..helper.string.jinja import is_probably_jinja
from ..config.config import show_advertisement

import asyncio
import copy
import datetime
import inspect
import jinja2
import os
import sys
import time


MAX_NAME_LENGTH = 20
MULTILINE_INDENT = ' ' * 8

TTask = TypeVar('TTask', bound='BaseTask')
TGroup = TypeVar('TGroup', bound='Group')


@typechecked
class Group():
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        parent: Optional[TGroup] = None
    ):
        self.name = name
        self.description = description
        self.parent = parent
        if parent is not None:
            parent.children.append(self)
        self.children: List[TGroup] = []
        self.tasks: List[TTask] = []

    def get_cmd_name(self) -> str:
        return to_cmd_name(self.name)

    def get_complete_name(self) -> str:
        cmd_name = self.get_cmd_name()
        if self.parent is None:
            return cmd_name
        parent_cmd_name = self.parent.get_complete_name()
        return f'{parent_cmd_name} {cmd_name}'

    def get_id(self) -> str:
        group_id = self.get_cmd_name()
        if self.parent is None:
            return group_id
        parent_group_id = self.parent.get_id()
        return f'{parent_group_id} {group_id}'


class AnyExtensionFileSystemLoader(jinja2.FileSystemLoader):
    def get_source(self, environment, template):
        for search_dir in self.searchpath:
            file_path = os.path.join(search_dir, template)
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    contents = file.read()
                return contents, file_path, lambda: False
        raise jinja2.TemplateNotFound(template)


@typechecked
class TimeTracker():

    def __init__(self):
        self._start_time: float = 0
        self._end_time: float = 0

    def start_timer(self):
        self._start_time = time.time()

    def end_timer(self):
        self._end_time = time.time()

    def get_elapsed_time(self) -> float:
        return self._end_time - self._start_time


@typechecked
class AttemptTracker():

    def __init__(self, retry: int = 2):
        self.retry = retry
        self._attempt: int = 1

    def get_max_attempt(self) -> int:
        return self.retry + 1

    def get_attempt(self) -> int:
        return self._attempt

    def increase_attempt(self):
        self._attempt += 1

    def should_attempt(self) -> bool:
        attempt = self.get_attempt()
        max_attempt = self.get_max_attempt()
        return attempt <= max_attempt

    def is_last_attempt(self) -> bool:
        attempt = self.get_attempt()
        max_attempt = self.get_max_attempt()
        return attempt >= max_attempt


@typechecked
class FinishTracker():

    def __init__(self):
        self._execution_queue: Optional[asyncio.Queue] = None
        self._counter = 0

    async def mark_start(self):
        if self._execution_queue is None:
            self._execution_queue = asyncio.Queue()
        self._counter += 1

    async def mark_as_done(self):
        # Tracker might be started several times
        # However, when the execution is marked as done, it applied globally
        # Thus, we need to send event as much as the counter.
        for i in range(self._counter):
            await self._execution_queue.put(True)

    async def is_done(self) -> bool:
        while self._execution_queue is None:
            await asyncio.sleep(0.05)
        return await self._execution_queue.get()


@typechecked
class PidModel():

    def __init__(self):
        self.zrb_task_pid: int = os.getpid()

    def set_task_pid(self, pid: int):
        self.zrb_task_pid = pid

    def get_task_pid(self) -> int:
        return self.zrb_task_pid


@typechecked
class TaskModel(
    PidModel, FinishTracker, AttemptTracker, TimeTracker
):
    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        retry: int = 2,
    ):
        # init properties
        self.name = name
        self.group = group
        self.envs = envs
        self.env_files = env_files
        self.icon = icon
        self.color = color
        # init parent classes
        PidModel.__init__(self)
        FinishTracker.__init__(self)
        TimeTracker.__init__(self)
        non_negative_retry = self.ensure_non_negative(
            retry, 'Find negative retry'
        )
        AttemptTracker.__init__(self, retry=non_negative_retry)
        # init private properties
        self._input_map: Mapping[str, Any] = {}
        self._env_map: Mapping[str, str] = {}
        self._complete_name: Optional[str] = None
        self._filled_complete_name: Optional[str] = None
        self._rendered_str: Mapping[str, str] = {}
        self._is_keyval_set = False  # Flag
        self._has_cli_interface = False
        self._render_data: Optional[Mapping[str, Any]] = None
        self._all_inputs: Optional[List[BaseInput]] = None

    def get_icon(self) -> str:
        if self.icon is None or self.icon == '':
            self.icon = get_random_icon()
        return self.icon

    def get_color(self) -> str:
        if self.color is None or not is_valid_color(self.color):
            self.color = get_random_color()
        return self.color

    def get_cmd_name(self) -> str:
        return to_cmd_name(self.name)

    def ensure_non_negative(self, value: float, error_label: str) -> float:
        if value < 0:
            self.log_warn(f'{error_label}: {value}')
            return 0
        return value

    def show_done_info(self):
        complete_name = self._get_complete_name()
        elapsed_time = self.get_elapsed_time()
        message = '\n'.join([
            f'{complete_name} completed in {elapsed_time} seconds',
        ])
        self.print_out_dark(message)
        self.play_bell()

    def log_debug(self, message: Any):
        prefix = self._get_log_prefix()
        colored_message = colored(
            f'{prefix} • {message}', attrs=['dark']
        )
        logger.debug(colored_message)

    def log_warn(self, message: Any):
        prefix = self._get_log_prefix()
        colored_message = colored(
            f'{prefix} • {message}', attrs=['dark']
        )
        logger.warning(colored_message)

    def log_info(self, message: Any):
        prefix = self._get_log_prefix()
        colored_message = colored(
            f'{prefix} • {message}', attrs=['dark']
        )
        logger.info(colored_message)

    def log_error(self, message: Any):
        prefix = self._get_log_prefix()
        colored_message = colored(
            f'{prefix} • {message}', color='red', attrs=['bold']
        )
        logger.error(colored_message, exc_info=True)

    def log_critical(self, message: Any):
        prefix = self._get_log_prefix()
        colored_message = colored(
            f'{prefix} • {message}', color='red', attrs=['bold']
        )
        logger.critical(colored_message, exc_info=True)

    def print_out(self, msg: Any):
        prefix = self._get_colored_print_prefix()
        print(f'🤖 ➜  {prefix} • {msg}'.rstrip(), file=sys.stderr)

    def print_err(self, msg: Any):
        prefix = self._get_colored_print_prefix()
        print(f'🤖 ⚠  {prefix} • {msg}'.rstrip(), file=sys.stderr)

    def print_out_dark(self, msg: Any):
        self.print_out(colored(msg, attrs=['dark']))

    def colored(self, text: str) -> str:
        return colored(text, color=self.get_color())

    def play_bell(self):
        print('\a', end='', file=sys.stderr)

    def _get_colored_print_prefix(self) -> str:
        return self.colored(self._get_print_prefix())

    def _get_print_prefix(self) -> str:
        common_prefix = self._get_common_prefix(show_time=True)
        icon = self.get_icon()
        truncated_name = self._get_filled_complete_name()
        return f'{common_prefix} • {icon} {truncated_name}'

    def _get_log_prefix(self) -> str:
        common_prefix = self._get_common_prefix(show_time=False)
        icon = self.get_icon()
        filled_name = self._get_filled_complete_name()
        return f'{common_prefix} • {icon} {filled_name}'

    def _get_common_prefix(self, show_time: bool) -> str:
        attempt = self.get_attempt()
        max_attempt = self.get_max_attempt()
        pid = self.get_task_pid()
        if show_time:
            now = datetime.datetime.now().isoformat()
            return f'{now} ⚙ {pid} ➤ {attempt} of {max_attempt}'
        return f'⚙ {pid} ➤ {attempt} of {max_attempt}'

    def _get_filled_complete_name(self) -> str:
        if self._filled_complete_name is not None:
            return self._filled_complete_name
        complete_name = self._get_complete_name()
        self._filled_complete_name = complete_name.rjust(MAX_NAME_LENGTH, ' ')
        return self._filled_complete_name

    def get_input_map(self) -> Mapping[str, Any]:
        return self._input_map

    def get_env_map(self) -> Mapping[str, str]:
        return self._env_map

    def _inject_env_map(
        self, env_map: Mapping[str, str], override: bool = False
    ):
        for key, val in env_map.items():
            if override or key not in self._env_map:
                self._env_map[key] = val

    def render_any(self, val: Any) -> Any:
        if isinstance(val, str):
            return self.render_str(val)
        return val

    def render_float(self, val: Union[str, float]) -> float:
        if isinstance(val, str):
            return float(self.render_str(val))
        return val

    def render_int(self, val: Union[str, int]) -> int:
        if isinstance(val, str):
            return int(self.render_str(val))
        return val

    def render_bool(self, val: Union[str, bool]) -> bool:
        if isinstance(val, str):
            return to_boolean(self.render_str(val))
        return val

    def render_str(self, val: str) -> str:
        if val in self._rendered_str:
            return self._rendered_str[val]
        if not is_probably_jinja(val):
            return val
        template = jinja2.Template(val)
        data = self._get_render_data()
        self.log_debug(f'Render string template: {val}, with data: {data}')
        try:
            rendered_text = template.render(data)
            self.log_debug(f'Get rendered result: {rendered_text}')
        except Exception:
            raise Exception(f'Fail to render "{val}" with data: {data}')
        self._rendered_str[val] = rendered_text
        return rendered_text

    def render_file(self, location: str) -> str:
        location_dir = os.path.dirname(location)
        env = jinja2.Environment(
            loader=AnyExtensionFileSystemLoader([location_dir])
        )
        template = env.get_template(location)
        data = self._get_render_data()
        data['TEMPLATE_DIR'] = location_dir
        self.log_debug(f'Render template file: {template}, with data: {data}')
        rendered_text = template.render(data)
        self.log_debug(f'Get rendered result: {rendered_text}')
        return rendered_text

    def _get_render_data(self) -> Mapping[str, Any]:
        if self._render_data is not None:
            return self._render_data
        render_data = dict(DEFAULT_RENDER_DATA)
        render_data.update({
            'env': self._env_map,
            'input': self._input_map,
        })
        self._render_data = render_data
        return render_data

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
        envs: List[Env] = self._deduplicate_env(self.envs)
        for env_file in reverse(self.env_files):
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

    def get_all_inputs(self) -> Iterable[BaseInput]:
        # Override this method!!!
        return self._all_inputs

    def _get_normalized_input_key(self, key: str) -> str:
        if key in RESERVED_INPUT_NAMES:
            return key
        return to_variable_name(key)

    def _get_complete_name(self) -> str:
        if self._complete_name is not None:
            return self._complete_name
        executable_prefix = ''
        if self._has_cli_interface:
            executable_prefix += self._get_executable_name() + ' '
        cmd_name = self.get_cmd_name()
        if self.group is None:
            self._complete_name = f'{executable_prefix}{cmd_name}'
            return self._complete_name
        group_cmd_name = self.group.get_complete_name()
        self._complete_name = f'{executable_prefix}{group_cmd_name} {cmd_name}'
        return self._complete_name

    def _get_executable_name(self) -> str:
        if len(sys.argv) > 0 and sys.argv[0] != '':
            return os.path.basename(sys.argv[0])
        return 'zrb'

    def set_has_cli_interface(self):
        self._has_cli_interface = True


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
        if group is not None:
            group.tasks.append(self)
        self.inputs = inputs
        self.description = description
        self.retry_interval = retry_interval
        self.upstreams = upstreams
        self.checkers = checkers
        self.checking_interval = checking_interval
        self.skip_execution = skip_execution
        self._is_check_triggered: bool = False
        self._is_checked: bool = False
        self._is_execution_triggered: bool = False
        self._is_execution_started: bool = False
        self._run_function: Optional[Callable[..., Any]] = run
        self._args: List[Any] = []
        self._kwargs: Mapping[str, Any] = {}

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
            inputs += upstream_inputs
        inputs += self.inputs
        self._all_inputs = ensure_uniqueness(
            inputs, lambda x, y: x.name == y.name
        )
        return inputs

    def get_description(self) -> str:
        if self.description != '':
            return self.description
        return self.name

    def create_main_loop(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., Any]:
        self.log_info('Create main loop')

        def main_loop(*args: Any, **kwargs: Any) -> Any:
            self.log_info('Copy task')
            self_cp = copy.deepcopy(self)
            return asyncio.run(self_cp._run_and_check_all(
                env_prefix=env_prefix,
                raise_error=raise_error,
                args=args,
                kwargs=kwargs
            ))
        return main_loop

    async def _run_and_check_all(
        self,
        env_prefix: str,
        raise_error: bool,
        args: Iterable[Any],
        kwargs: Mapping[str, Any]
    ):
        self.start_timer()
        self.log_info('Set keyval')
        await self._set_keyval(kwargs=kwargs, env_prefix=env_prefix)
        self.log_info('Get new kwargs')
        new_kwargs = self.get_input_map()
        # make sure args and kwargs['_args'] are the same
        self.log_info('Get new args')
        new_args = copy.deepcopy(args)
        if len(args) == 0 and '_args' in kwargs:
            new_args = kwargs['_args']
        new_kwargs['_args'] = new_args
        # inject self as kwargs['_task']
        new_kwargs['_task'] = self
        self._args = new_args
        self._kwargs = new_kwargs
        # run the task
        try:
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
            self.play_bell()

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
            await asyncio.sleep(self.checking_interval)
        self.end_timer()
        self.log_info('Task is ready')
        if show_info:
            if show_advertisement:
                selected_advertisement = get_advertisement(advertisements)
                selected_advertisement.show()
            self.show_done_info()
            self.show_run_command()
        return True

    def show_run_command(self):
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
            while not self._is_checked:
                await asyncio.sleep(0.1)
            return True
        self._is_check_triggered = True
        self.log_debug('Start checking')
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
        self.log_debug('Waiting execution to be started')
        while not self._is_execution_started:
            # Don't start checking before the execution itself has been started
            await asyncio.sleep(0.1)
        check_coroutines: Iterable[asyncio.Task] = []
        for checker_task in self.checkers:
            check_coroutines.append(
                asyncio.create_task(checker_task._run_all())
            )
        await asyncio.gather(*check_coroutines)
        return True

    async def _run_all(self, *args: Any, **kwargs: Any) -> Any:
        self.log_info('Start running')
        await self.mark_start()
        coroutines: Iterable[asyncio.Task] = []
        # Add upstream tasks to processes
        for upstream_task in self.upstreams:
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
            self.log_debug('Skip execution because execution flag is True')
            return
        self.log_debug('Set execution flag to True')
        self._is_execution_triggered = True
        self.log_debug('Start running')
        # get upstream checker
        upstream_check_processes: Iterable[asyncio.Task] = []
        for upstream_task in self.upstreams:
            upstream_check_processes.append(asyncio.create_task(
                upstream_task._loop_check()
            ))
        # wait all upstream checkers to complete
        await asyncio.gather(*upstream_check_processes)
        # mark execution as started, so that checkers can start checking
        self._is_execution_started = True
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
        upstream_coroutines = []
        # set uplstreams keyval
        for upstream_task in self.upstreams:
            upstream_coroutines.append(asyncio.create_task(
                upstream_task._set_keyval(
                    kwargs=new_kwargs, env_prefix=env_prefix
                )
            ))
        # set checker keyval
        local_env_map = self.get_env_map()
        checker_coroutines = []
        for checker_task in self.checkers:
            checker_task.inputs += self.inputs
            checker_task._inject_env_map(local_env_map, override=True)
            checker_coroutines.append(asyncio.create_task(
                checker_task._set_keyval(
                    kwargs=new_kwargs, env_prefix=env_prefix
                )
            ))
        # wait for checker and upstreams
        coroutines = checker_coroutines + upstream_coroutines
        await asyncio.gather(*coroutines)
