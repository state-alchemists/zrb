from typing import Any, List, Mapping, Optional, Union
from pydantic import BaseModel
from jinja2 import Template
from ..helper.accessories.color import (
    get_random_color, is_valid_color, colored
)
from ..helper.accessories.icon import get_random_icon
from ..helper.keyval.get_object_from_keyval import get_object_from_keyval
from ..helper.string.string import get_cmd_name
from ..task_env.env import Env

import datetime
import logging
import os
import sys
import time


class TimeTracker(BaseModel):
    zrb_start_time: float = 0
    zrb_end_time: float = 0

    def reset_timer(self):
        self.zrb_start_time = 0
        self.zrb_end_time = 0

    def start_timer(self):
        self.zrb_start_time = time.time()

    def end_timer(self):
        self.zrb_end_time = time.time()

    def get_elapsed_time(self) -> float:
        return self.zrb_end_time - self.zrb_start_time


class AttemptTracker(BaseModel):
    retry: int = 2

    zrb_attempt: int = 1

    def get_max_attempt(self) -> int:
        return self.retry + 1

    def get_attempt(self) -> int:
        return self.zrb_attempt

    def increase_attempt(self):
        self.zrb_attempt += 1

    def reset_attempt(self):
        self.zrb_attempt = 0

    def should_attempt(self) -> bool:
        attempt = self.get_attempt()
        max_attempt = self.get_max_attempt()
        return attempt <= max_attempt

    def is_last_attempt(self) -> bool:
        attempt = self.get_attempt()
        max_attempt = self.get_max_attempt()
        return attempt >= max_attempt


class FinishTracker(BaseModel):
    zrb_is_done: bool = False

    def mark_as_done(self):
        self.zrb_is_done = True

    def mark_as_undone(self):
        self.zrb_is_done = False

    def is_done(self) -> bool:
        return self.zrb_is_done


class PidModel(BaseModel):
    zrb_task_pid: int = os.getpid()

    def set_task_pid(self, pid: int):
        self.zrb_task_pid = pid

    def get_task_pid(self) -> int:
        return self.zrb_task_pid


class AccessoriesModel(BaseModel):
    name: str
    icon: Optional[str] = None
    color: Optional[str] = None

    def get_icon(self) -> str:
        if self.icon is None or self.icon == '':
            self.icon = get_random_icon()
        return self.icon

    def get_color(self) -> str:
        if self.color is None or not is_valid_color(self.color):
            self.color = get_random_color()
        return self.color

    def get_cmd_name(self) -> str:
        return get_cmd_name(self.name)

    def log_debug(self, message: Any) -> str:
        prefix = self._get_log_prefix()
        colored_message = colored(
            f'{prefix}: {message}', attrs=['dark']
        )
        logging.debug(colored_message)

    def log_warn(self, message: Any) -> str:
        prefix = self._get_log_prefix()
        colored_message = colored(
            f'{prefix}: {message}', attrs=['dark']
        )
        logging.warn(colored_message)

    def log_info(self, message: Any) -> str:
        prefix = self._get_log_prefix()
        colored_message = colored(
            f'{prefix}: {message}', attrs=['dark']
        )
        logging.info(colored_message)

    def log_error(self, message: Any) -> str:
        prefix = self._get_log_prefix()
        colored_message = colored(
            f'{prefix}: {message}', color='red', attrs=['bold']
        )
        logging.error(colored_message, exc_info=True)

    def print_out(self, msg: Any):
        prefix = self._get_colored_log_prefix()
        print(f'🤖 ➜ {prefix} {msg}'.rstrip())

    def print_err(self, msg: Any):
        prefix = self._get_colored_log_prefix()
        print(f'🤖 ⚠ {prefix} {msg}'.rstrip(), file=sys.stderr)

    def colored(self, text: str) -> str:
        return colored(text, color=self.get_color())

    def play_bell(self):
        print('\a')

    def _get_colored_log_prefix(self) -> str:
        return self.colored(self._get_log_prefix())

    def _get_log_prefix(self) -> str:
        '''
        Return log prefix representing current task.
        To be overriden later
        '''
        return ''


class TaskModel(
    TimeTracker, AttemptTracker, FinishTracker, PidModel,
    AccessoriesModel
):

    envs: List[Env] = []

    zrb_input_map: Mapping[str, Any] = {}
    zrb_env_map: Mapping[str, str] = {}
    zrb_is_keyval_set = False  # Flag

    def get_input_map(self) -> Mapping[str, Any]:
        return self.zrb_input_map

    def get_env_map(self) -> Mapping[str, str]:
        env_map = os.environ
        env_map.update(self.zrb_env_map)
        return env_map

    def inject_env_map(self, env_map: Mapping[str, str]):
        for key, val in env_map.items():
            if key not in self.zrb_env_map:
                self.zrb_env_map[key] = val

    def render_str(self, text: str) -> str:
        template = Template(text)
        data = {
            'env': get_object_from_keyval(self.zrb_env_map),
            'input': get_object_from_keyval(self.zrb_input_map),
        }
        self.log_debug(f'Render template: {text}\nWith data: {data}')
        rendered_text = template.render(data)
        self.log_debug(f'Rendered text: {rendered_text}')
        return rendered_text

    def render_float(self, val: Union[str, float]) -> float:
        if isinstance(val, str):
            return float(self.render_str(val))
        return val

    def render_int(self, val: Union[str, int]) -> int:
        if isinstance(val, str):
            return int(self.render_str(val))
        return val

    def set_local_keyval(
        self,
        input_map: Mapping[str, Any],
        env_prefix: str = ''
    ):
        if self.zrb_is_keyval_set:
            return True
        self.zrb_is_keyval_set = True
        self.zrb_input_map = dict(input_map)
        self.log_debug(f'Input map: {self.zrb_input_map}')
        self.zrb_env_map = {}
        for task_env in self.envs:
            env_name = task_env.name
            env_value = task_env.get(env_prefix)
            self.zrb_env_map[env_name] = env_value
        self.log_debug(f'Env map: {self.zrb_env_map}')

    def _get_log_prefix(self) -> str:
        '''
        Return log prefix representing current task.
        This implementation override AccessoriesModel.get_log_prefix.
        '''
        attempt = self.get_attempt()
        max_attempt = self.get_max_attempt()
        now = datetime.datetime.now().isoformat()
        pid = self.get_task_pid()
        info = f'{now} ⚙ {pid} ➤ {attempt} of {max_attempt}'
        icon = self.get_icon()
        name = self.name
        return f'{info} | {icon} {name}'

    def show_celebration(self):
        task_name = self.name
        elapsed_time = self.get_elapsed_time()
        print('🤖 🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉')
        print(f'🤖 {task_name} completed in {elapsed_time} seconds')
        print('🤖 🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉')
        self.play_bell()
