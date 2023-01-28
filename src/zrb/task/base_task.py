from typing import Any, List, Mapping, Optional, TypeVar
from pydantic import BaseModel
from ..task_input.base_input import BaseInput
from ..task_env.env import Env
from ..helper.random_maker import get_random_icon, get_random_color
from termcolor import colored, COLORS

import asyncio
import datetime
import logging
import os
import sys

Task = TypeVar('Task', bound='BaseTask')


class BaseTask(BaseModel):
    name: str
    icon: Optional[str] = None
    color: Optional[str] = None
    inputs: List[BaseInput] = []
    envs: List[Env] = []
    upstreams: List[Task] = []
    readiness_probes: List[Task] = []
    checking_interval: int = 1
    retry: int = 2
    retry_interval: int = 1

    # internal private values
    zrb_attempt: int = 1
    zrb_is_done: bool = False
    zrb_task_pid: int = os.getpid()
    zrb_input_map: Mapping[str, Any] = {}  # suppose to set once
    zrb_env_map: Mapping[str, str] = {}  # suppose to be set once
    zrb_sys_env_map: Mapping[str, str] = {}

    def get_icon(self) -> str:
        '''
        Getting task icon
        '''
        if self.icon is None or self.icon == '':
            self.icon = get_random_icon()
        return self.icon

    def get_color(self) -> str:
        if self.color is None or self.color not in COLORS:
            self.color = get_random_color()
        return self.color

    def get_cmd_name(self) -> str:
        '''
        Getting task cmd name
        '''
        return self.name

    def get_inputs(self) -> List[BaseInput]:
        ''''
        Getting inputs of this task
        '''
        inputs: List[BaseInput] = []
        for upstream in self.upstreams:
            upstream_inputs = upstream.get_inputs()
            inputs = inputs + upstream_inputs
        inputs = inputs + self.inputs
        return inputs

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

    async def run(self, *args: Any, **kwargs: Any):
        '''
        Override task running logic
        '''
        self.log_debug(
            f'Run with args {args} and kwargs {kwargs}'
        )

    async def check(self) -> bool:
        '''
        Override task checking logic
        '''
        # return zrb._is_done signal
        return self.zrb_is_done

    async def _check(self) -> bool:
        while not await self._check_current_task():
            self.log_debug('Task is not ready')
            await asyncio.sleep(self.checking_interval)
        self.log_debug('Task is ready')
        return True

    async def _check_current_task(self) -> bool:
        if len(self.readiness_probes) == 0:
            # There is no readiness probes defined
            # Just wait for self.check to be completed
            return await self.check()
        # There are readiness probes
        processes: List[asyncio.Task] = []
        for readiness_task in self.readiness_probes:
            processes.append(readiness_task.run())
        await asyncio.gather(*processes)

    async def _run(self, *args: Any, **kwargs: Any):
        processes: List[asyncio.Task] = []
        for upstream_task in self.upstreams:
            processes.append(upstream_task._run(*args, **kwargs))
        processes.append(self._run_current_task(*args, **kwargs))
        await asyncio.gather(*processes)

    async def _run_current_task(self, *args, **kwargs: Any):
        await self._check_upstream()
        await self._run_with_retry(*args, **kwargs)

    async def _check_upstream(self):
        processes: List[asyncio.Task] = []
        for upstream_task in self.upstreams:
            processes.append(upstream_task._check())
        await asyncio.gather(*processes)

    async def _run_with_retry(self, *args, **kwargs):
        max_attempt = self.retry + 1
        retrying = True
        while self.zrb_attempt <= max_attempt:
            try:
                await self.run(*args, **kwargs)
                retrying = False
            except Exception:
                self.log_error('Encounter error')
                if self.zrb_attempt == max_attempt:
                    raise
                self.zrb_attempt = self.zrb_attempt + 1
                await asyncio.sleep(self.retry_interval)
            if not retrying:
                break
        # By default, self.check() will return the value of is_done property
        # Here we indicate that the task has been successfully performed
        self.zrb_is_done = True

    def _set_map(
        self, input_map: Mapping[str, Any],
        sys_env_map: Mapping[str, str],
        env_prefix: str
    ):
        self.zrb_input_map = dict(input_map)
        self.zrb_sys_env_map = dict(sys_env_map)
        # set zrb_env_map
        for task_env in self.envs:
            env_name = task_env.name
            env_value = task_env.get(env_prefix)
            self.zrb_env_map[env_name] = env_value
        # share zrb_input_map and zrb_sys_env_map to upstreams
        for upstream_task in self.upstreams:
            upstream_task._set_map(
                input_map=input_map,
                sys_env_map=sys_env_map,
                env_prefix=env_prefix
            )
        # share zrb_input_map and zrb_sys_env_map to readiness_probes
        for readiness_task in self.readiness_probes:
            readiness_task._set_map(
                input_map=input_map,
                sys_env_map=sys_env_map,
                env_prefix=env_prefix
            )

    def _get_colored_log_prefix(self) -> str:
        return colored(self._get_log_prefix(), color=self.get_color())

    def _get_log_prefix(self) -> str:
        attempt = self.zrb_attempt
        max_attempt = self.retry + 1
        now = datetime.datetime.now().isoformat()
        pid = self.zrb_task_pid
        info = f'{now} ⚙ {pid} ➤ {attempt} of {max_attempt}'
        icon = self.get_icon()
        name = self.name
        return f'{info} | {icon} {name}'
