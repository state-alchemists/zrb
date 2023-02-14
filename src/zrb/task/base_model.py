from typing import Any, Iterable, Mapping, Optional, Union
from typeguard import typechecked
from ..helper.accessories.color import (
    get_random_color, is_valid_color, colored
)
from ..helper.accessories.icon import get_random_icon
from ..helper.string.conversion import (
    to_cmd_name, to_variable_name
)
from ..helper.render_data import DEFAULT_RENDER_DATA
from ..helper.log import logger
from ..task_env.env import Env
from ..task_group.group import Group
from ..task_input._constant import RESERVED_INPUT_NAMES

import datetime
import os
import sys
import time
import jinja2


MAX_NAME_LENGTH = 20
MULTILINE_INDENT = ' ' * 8


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

    def reset_timer(self):
        self._start_time = 0
        self._end_time = 0

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

    def reset_attempt(self):
        self._attempt = 0

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
        self._is_done: bool = False

    def mark_as_done(self):
        self._is_done = True

    def mark_as_undone(self):
        self._is_done = False

    def is_done(self) -> bool:
        return self._is_done


@typechecked
class PidModel():

    def __init__(self):
        self.zrb_task_pid: int = os.getpid()

    def set_task_pid(self, pid: int):
        self.zrb_task_pid = pid

    def get_task_pid(self) -> int:
        return self.zrb_task_pid


@typechecked
class TaskDataModel():

    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        envs: Iterable[Env] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
    ):
        self.name = name
        self.group = group
        self.envs = envs
        for key in dict(os.environ):
            self.envs.append(Env(name=key, os_name=key))
        self.icon = icon
        self.color = color
        self._input_map: Mapping[str, Any] = {}
        self._env_map: Mapping[str, str] = {}
        self._complete_name: Optional[str] = None
        self._is_keyval_set = False  # Flag

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

    def print_out(self, msg: Any):
        prefix = self._get_colored_print_prefix()
        print(f'🤖 ➜  {prefix} • {msg}'.rstrip(), file=sys.stderr)

    def print_err(self, msg: Any):
        prefix = self._get_colored_print_prefix()
        print(f'🤖 ⚠  {prefix} • {msg}'.rstrip(), file=sys.stderr)

    def colored(self, text: str) -> str:
        return colored(text, color=self.get_color())

    def play_bell(self):
        print('\a', end='', file=sys.stderr)

    def _get_colored_print_prefix(self) -> str:
        return self.colored(self._get_print_prefix())

    def _get_print_prefix(self) -> str:
        common_prefix = self._get_common_prefix(show_time=True)
        icon = self.get_icon()
        truncated_name = self._get_truncated_complete_name()
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
        return self._get_complete_name().rjust(MAX_NAME_LENGTH, ' ')

    def _get_truncated_complete_name(self):
        filled_name = self._get_filled_complete_name()
        if len(filled_name) > MAX_NAME_LENGTH:
            return '..' + filled_name[-(MAX_NAME_LENGTH-2):]
        return filled_name

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

    def get_float(self, val: Union[str, float]) -> float:
        if isinstance(val, str):
            return float(self.render_str(val))
        return val

    def get_int(self, val: Union[str, int]) -> int:
        if isinstance(val, str):
            return int(self.render_str(val))
        return val

    def get_bool(self, val: Union[str, bool]) -> bool:
        if isinstance(val, str):
            str_val = self.render_str(val)
            if str_val.lower() in ['true', '1', 'yes', 'y', 'active']:
                return True
            if str_val.lower() in ['false', '0', 'no', 'n', 'inactive']:
                return False
            raise Exception(f'Cannot infer boolean value from {str_val}')
        return val

    def render_str(self, val: str) -> str:
        template = jinja2.Template(val)
        data = self._get_render_data()
        self.log_debug(f'Render string template: {val}, with data: {data}')
        rendered_text = template.render(data)
        self.log_debug(f'Get rendered result: {rendered_text}')
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
        render_data = dict(DEFAULT_RENDER_DATA)
        render_data.update({
            'env': self._env_map,
            'input': self._input_map,
        })
        return render_data

    def _get_multiline_repr(self, text: str) -> str:
        lines_repr: Iterable[str] = []
        for index, line in enumerate(text.split('\n')):
            line_number_repr = str(index + 1).rjust(4, '0')
            lines_repr.append(f'{MULTILINE_INDENT}{line_number_repr} | {line}')
        return '\n'.join(lines_repr)

    def _set_local_keyval(
        self,
        input_map: Mapping[str, Any],
        env_prefix: str = ''
    ):
        if self._is_keyval_set:
            return True
        self._is_keyval_set = True
        self._input_map: Mapping[str, Any]
        for input_name, val in input_map.items():
            self._input_map[self._get_normalized_input_key(input_name)] = val
        self.log_debug(f'Set input map: {self._input_map}')
        self._env_map = dict(os.environ)
        for task_env in self.envs:
            env_name = task_env.name
            env_value = task_env.get(env_prefix)
            if '{{' in env_value and '}}' in env_value:
                env_value = self.render_str(env_value)
            self._env_map[env_name] = env_value
        self.log_debug(f'Set env map: {self._env_map}')

    def _get_normalized_input_key(self, key: str) -> str:
        if key in RESERVED_INPUT_NAMES:
            return key
        return to_variable_name(key)

    def _get_complete_name(self) -> str:
        if self._complete_name is not None:
            return self._complete_name
        executable_name = self._get_executable_name()
        cmd_name = self.get_cmd_name()
        if self.group is None:
            self._complete_name = f'{executable_name} {cmd_name}'
            return self._complete_name
        group_cmd_name = self.group.get_complete_name()
        self._complete_name = f'{executable_name} {group_cmd_name} {cmd_name}'
        return self._complete_name

    def _get_executable_name(self) -> str:
        if len(sys.argv) > 0 and sys.argv[0] != '':
            return os.path.basename(sys.argv[0])
        return 'zrb'


@typechecked
class TaskModel(
    TaskDataModel, PidModel, FinishTracker, AttemptTracker, TimeTracker
):

    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        envs: Iterable[Env] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        retry: int = 2,
    ):
        TaskDataModel.__init__(
            self,
            name=name,
            group=group,
            envs=envs,
            icon=icon,
            color=color
        )
        retry = self.ensure_non_negative(retry, 'Find negative retry')
        PidModel.__init__(self)
        FinishTracker.__init__(self)
        AttemptTracker.__init__(self, retry=retry)
        TimeTracker.__init__(self)

    def ensure_non_negative(self, value: float, error_label: str) -> float:
        if value < 0:
            self.log_warn(
                f'{error_label}: {value}'
            )
            return 0
        return value

    def show_celebration(self):
        complete_name = self._get_complete_name()
        elapsed_time = self.get_elapsed_time()
        message = '\n'.join([
            f'{complete_name} completed in {elapsed_time} seconds',
        ])
        print(colored(message, attrs=['dark']), file=sys.stderr)
        self.play_bell()
