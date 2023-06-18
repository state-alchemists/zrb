from typing import Any, Callable, Iterable, Optional, Union
from typeguard import typechecked
from .base_task import BaseTask, Group
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_input.base_input import BaseInput

import asyncio
import os


@typechecked
class PathChecker(BaseTask):

    def __init__(
        self,
        name: str = 'path-check',
        group: Optional[Group] = None,
        inputs: Iterable[BaseInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        path: str = '',
        upstreams: Iterable[BaseTask] = [],
        checking_interval: float = 0.1,
        show_error_interval: float = 5,
        skip_execution: Union[bool, str, Callable[..., bool]] = False
    ):
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
            checkers=[],
            checking_interval=checking_interval,
            retry=0,
            retry_interval=0,
            skip_execution=skip_execution,
        )
        self._path = path
        self._show_error_interval = show_error_interval

    def create_main_loop(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., bool]:
        return super().create_main_loop(env_prefix, raise_error)

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        path = self.render_str(self._path)
        wait_time = 0
        while not self._check_path(
            path=path,
            should_print_error=wait_time >= self._show_error_interval
        ):
            if wait_time >= self._show_error_interval:
                wait_time = 0
            await asyncio.sleep(self._checking_interval)
            wait_time += self._checking_interval
        return True

    def _check_path(
        self, path: str, should_print_error: bool
    ) -> bool:
        label = self._get_label(path)
        try:
            if os.path.exists(path):
                self.print_out(f'{label} (Exist)')
                return True
            self._debug_and_print_error(
                f'{label} (Not Exist)', should_print_error
            )
        except Exception:
            self._debug_and_print_error(
                f'{label} Socket error', should_print_error
            )
        return False

    def _debug_and_print_error(self, message: str, should_print_error: bool):
        if should_print_error:
            self.print_err(message)
        self.log_debug(message)

    def _get_label(self, path: str) -> str:
        return f'Checking {path}'
