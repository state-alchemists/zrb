from zrb.helper.typing import (
    Any, Callable, Iterable, List, Mapping, Optional, Union
)
from zrb.helper.typecheck import typechecked
from zrb.config.config import show_time
from zrb.task.any_task import AnyTask
from zrb.helper.string.conversion import to_boolean, to_cmd_name
from zrb.helper.string.jinja import is_probably_jinja
from zrb.helper.render_data import DEFAULT_RENDER_DATA
from zrb.helper.log import logger
from zrb.helper.accessories.color import colored, get_random_color
from zrb.helper.accessories.icon import get_random_icon
from zrb.helper.util import coalesce_str
from zrb.task_input.any_input import AnyInput
from zrb.task_group.group import Group
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile

import asyncio
import datetime
import os
import time
import jinja2
import sys

LOG_NAME_LENGTH = 20


@typechecked
class CommonTaskModel():
    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        description: str = '',
        inputs: List[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0,
        run: Optional[Callable[..., Any]] = None,
        skip_execution: Union[bool, str, Callable[..., bool]] = False
    ):
        self._name = name
        self._group = group
        if group is not None:
            group.add_task(self)
        self._description = coalesce_str(description, name)
        self._inputs = inputs
        self._envs = envs
        self._env_files = env_files
        self._icon = coalesce_str(icon, get_random_icon())
        self._color = coalesce_str(color, get_random_color())
        self._retry = retry
        self._retry_interval = retry_interval
        self._upstreams = upstreams
        self._checkers = checkers
        self._checking_interval = checking_interval
        self._run_function: Optional[Callable[..., Any]] = run
        self._skip_execution = skip_execution
        self._allow_add_envs = True
        self._allow_add_env_files = True
        self._allow_add_inputs = True

    def set_name(self, new_name: str):
        if self._description == self._name:
            self._description = new_name
        self._name = new_name

    def set_description(self, new_description: str):
        self._description = new_description

    def set_icon(self, new_icon: str):
        self._icon = new_icon

    def set_color(self, new_color: str):
        self._color = new_color

    def set_retry(self, new_retry: int):
        self._retry = new_retry

    def set_skip_execution(
        self, skip_execution: Union[bool, str, Callable[..., bool]]
    ):
        self._skip_execution = skip_execution

    def set_retry_interval(self, new_retry_interval: Union[float, int]):
        self._retry_interval = new_retry_interval

    def set_checking_interval(self, new_checking_interval: Union[float, int]):
        self._checking_interval = new_checking_interval

    def add_inputs(self, *inputs: AnyInput):
        if not self._allow_add_inputs:
            raise Exception(f'Cannot add inputs on `{self._name}`')
        self._inputs += inputs

    def add_envs(self, *envs: Env):
        if not self._allow_add_envs:
            raise Exception(f'Cannot add envs on `{self._name}`')
        self._envs += envs

    def add_env_files(self, *env_files: EnvFile):
        if not self._allow_add_env_files:
            raise Exception(f'Cannot add env_files on `{self._name}`')
        self._env_files += env_files

    def get_icon(self) -> str:
        return self._icon

    def get_color(self) -> str:
        return self._color

    def get_env_files(self) -> List[EnvFile]:
        return self._env_files

    def get_envs(self) -> List[Env]:
        return self._envs

    def get_inputs(self) -> List[AnyInput]:
        return self._inputs

    def get_checkers(self) -> Iterable[AnyTask]:
        return self._checkers

    def get_upstreams(self) -> Iterable[AnyTask]:
        return self._upstreams

    def get_description(self) -> str:
        return self._description

    def get_cmd_name(self) -> str:
        return to_cmd_name(self._name)


@typechecked
class TimeTracker():

    def __init__(self):
        self.__start_time: float = 0
        self.__end_time: float = 0

    def _start_timer(self):
        self.__start_time = time.time()

    def _end_timer(self):
        self.__end_time = time.time()

    def _get_elapsed_time(self) -> float:
        return self.__end_time - self.__start_time


@typechecked
class AttemptTracker():

    def __init__(self, retry: int = 2):
        self.__retry = retry
        self.__attempt: int = 1
        self.__no_more_attempt: bool = False

    def _get_max_attempt(self) -> int:
        return self.__retry + 1

    def _get_attempt(self) -> int:
        return self.__attempt

    def _increase_attempt(self):
        self.__attempt += 1

    def _should_attempt(self) -> bool:
        attempt = self._get_attempt()
        max_attempt = self._get_max_attempt()
        return attempt <= max_attempt

    def _is_last_attempt(self) -> bool:
        attempt = self._get_attempt()
        max_attempt = self._get_max_attempt()
        return attempt >= max_attempt


@typechecked
class FinishTracker():

    def __init__(self):
        self.__execution_queue: Optional[asyncio.Queue] = None
        self.__counter = 0

    async def _mark_awaited(self):
        if self.__execution_queue is None:
            self.__execution_queue = asyncio.Queue()
        self.__counter += 1

    async def _mark_done(self):
        # Tracker might be started several times
        # However, when the execution is marked as done, it applied globally
        # Thus, we need to send event as much as the counter.
        for i in range(self.__counter):
            await self.__execution_queue.put(True)

    async def _is_done(self) -> bool:
        while self.__execution_queue is None:
            await asyncio.sleep(0.05)
        return await self.__execution_queue.get()


@typechecked
class PidModel():

    def __init__(self):
        self.__task_pid: int = os.getpid()

    def _set_task_pid(self, pid: int):
        self.__task_pid = pid

    def _get_task_pid(self) -> int:
        return self.__task_pid


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
class Renderer():

    def __init__(self):
        self.__input_map: Mapping[str, Any] = {}
        self.__env_map: Mapping[str, str] = {}
        self.__render_data: Optional[Mapping[str, Any]] = None
        self.__rendered_str: Mapping[str, str] = {}

    def get_input_map(self) -> Mapping[str, Any]:
        # This return reference to input map, so input map can be updated
        return self.__input_map

    def _set_input_map(self, key: str, val: Any):
        self.__input_map[key] = val

    def get_env_map(self) -> Mapping[str, str]:
        # This return reference to env map, so env map can be updated
        return self.__env_map

    def _set_env_map(self, key: str, val: str):
        self.__env_map[key] = val

    def render_any(
        self, val: Any, data: Optional[Mapping[str, Any]] = None
    ) -> Any:
        if isinstance(val, str):
            return self.render_str(val, data)
        return val

    def render_float(
        self, val: Union[str, float], data: Optional[Mapping[str, Any]] = None
    ) -> float:
        if isinstance(val, str):
            return float(self.render_str(val, data))
        return val

    def render_int(
        self, val: Union[str, int], data: Optional[Mapping[str, Any]] = None
    ) -> int:
        if isinstance(val, str):
            return int(self.render_str(val, data))
        return val

    def render_bool(
        self, val: Union[str, bool], data: Optional[Mapping[str, Any]] = None
    ) -> bool:
        if isinstance(val, str):
            return to_boolean(self.render_str(val, data))
        return val

    def render_str(
        self, val: str, data: Optional[Mapping[str, Any]] = None
    ) -> str:
        if val in self.__rendered_str:
            return self.__rendered_str[val]
        if not is_probably_jinja(val):
            return val
        template = jinja2.Template(val)
        render_data = self._get_render_data(additional_data=data)
        try:
            rendered_text = template.render(render_data)
        except Exception:
            raise Exception(f'Fail to render "{val}" with data: {render_data}')
        self.__rendered_str[val] = rendered_text
        return rendered_text

    def render_file(
        self, location: str, data: Optional[Mapping[str, Any]] = None
    ) -> str:
        location_dir = os.path.dirname(location)
        env = jinja2.Environment(
            loader=AnyExtensionFileSystemLoader([location_dir])
        )
        template = env.get_template(location)
        render_data = self._get_render_data(additional_data=data)
        render_data['TEMPLATE_DIR'] = location_dir
        rendered_text = template.render(render_data)
        return rendered_text

    def _get_render_data(
        self, additional_data: Optional[Mapping[str, Any]] = None
    ) -> Mapping[str, Any]:
        self._ensure_cached_render_data()
        if additional_data is None:
            return self.__render_data
        return {**self.__render_data, **additional_data}

    def _ensure_cached_render_data(self):
        if self.__render_data is not None:
            return self.__render_data
        render_data = dict(DEFAULT_RENDER_DATA)
        render_data.update({
            'env': self.__env_map,
            'input': self.__input_map,
        })
        self.__render_data = render_data
        return render_data


@typechecked
class TaskModelWithPrinterAndTracker(
    CommonTaskModel, PidModel, TimeTracker
):
    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        description: str = '',
        inputs: List[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        retry: int = 2,
        retry_interval: Union[int, float] = 1,
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[int, float] = 0,
        run: Optional[Callable[..., Any]] = None,
        skip_execution: Union[bool, str, Callable[..., bool]] = False

    ):
        self._filled_complete_name: Optional[str] = None
        self._has_cli_interface = False
        self._complete_name: Optional[str] = None
        CommonTaskModel.__init__(
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
        PidModel.__init__(self)
        TimeTracker.__init__(self)

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

    def print_out(self, message: Any, trim_message: bool = True):
        prefix = self._get_colored_print_prefix()
        message_str = f'{message}'.rstrip() if trim_message else f'{message}'
        print(f'🤖 ○ {prefix} • {message_str}', file=sys.stderr)
        sys.stderr.flush()

    def print_err(self, message: Any, trim_message: bool = True):
        prefix = self._get_colored_print_prefix()
        message_str = f'{message}'.rstrip() if trim_message else f'{message}'
        print(f'🤖 △ {prefix} • {message_str}', file=sys.stderr)
        sys.stderr.flush()

    def print_out_dark(self, message: Any, trim_message: bool = True):
        message_str = f'{message}'
        self.print_out(colored(message_str, attrs=['dark']), trim_message)

    def _play_bell(self):
        print('\a', end='', file=sys.stderr)

    def _get_colored_print_prefix(self) -> str:
        return self._get_colored(self._get_print_prefix())

    def _get_colored(self, text: str) -> str:
        return colored(text, color=self.get_color())

    def _get_print_prefix(self) -> str:
        common_prefix = self._get_common_prefix(show_time=show_time)
        icon = self.get_icon()
        truncated_name = self._get_filled_complete_name()
        return f'{common_prefix} {icon} {truncated_name}'

    def _get_log_prefix(self) -> str:
        common_prefix = self._get_common_prefix(show_time=False)
        icon = self.get_icon()
        filled_name = self._get_filled_complete_name()
        return f'{common_prefix} {icon} {filled_name}'

    def _get_common_prefix(self, show_time: bool) -> str:
        attempt = self._get_attempt()
        max_attempt = self._get_max_attempt()
        pid = self._get_task_pid()
        if show_time:
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            return f'◷ {now} ❁ {pid} → {attempt}/{max_attempt}'
        return f'❁ {pid} → {attempt}/{max_attempt}'

    def _get_filled_complete_name(self) -> str:
        if self._filled_complete_name is not None:
            return self._filled_complete_name
        complete_name = self._get_complete_name()
        self._filled_complete_name = complete_name.rjust(LOG_NAME_LENGTH, ' ')
        return self._filled_complete_name

    def _get_complete_name(self) -> str:
        if self._complete_name is not None:
            return self._complete_name
        executable_prefix = ''
        if self._has_cli_interface:
            executable_prefix += self._get_executable_name() + ' '
        cmd_name = self.get_cmd_name()
        if self._group is None:
            self._complete_name = f'{executable_prefix}{cmd_name}'
            return self._complete_name
        group_cmd_name = self._group.get_complete_name()
        self._complete_name = f'{executable_prefix}{group_cmd_name} {cmd_name}'
        return self._complete_name

    def _get_executable_name(self) -> str:
        if len(sys.argv) > 0 and sys.argv[0] != '':
            return os.path.basename(sys.argv[0])
        return 'zrb'

    def set_has_cli_interface(self):
        self._has_cli_interface = True
