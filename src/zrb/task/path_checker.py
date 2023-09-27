from zrb.helper.typing import Any, Callable, Iterable, Optional, Union, TypeVar
from zrb.helper.typecheck import typechecked
from zrb.task.base_task import BaseTask
from zrb.task.any_task import AnyTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

import asyncio
import os

TPathChecker = TypeVar('TPathChecker', bound='PathChecker')


@typechecked
class PathChecker(BaseTask):

    def __init__(
        self,
        name: str = 'path-check',
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        path: str = '',
        upstreams: Iterable[AnyTask] = [],
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

    def copy(self) -> TPathChecker:
        return super().copy()

    def to_function(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., bool]:
        return super().to_function(env_prefix, raise_error)

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

    def __repr__(self) -> str:
        return f'<PathChecker name={self._name}>'
