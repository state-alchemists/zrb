from zrb.helper.typing import Any, Callable, Iterable, Optional, Union, TypeVar
from zrb.helper.typecheck import typechecked
from zrb.task.base_task import BaseTask
from zrb.task.any_task import AnyTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

import socket
import asyncio

TPortChecker = TypeVar('TPortChecker', bound='PortChecker')


@typechecked
class PortChecker(BaseTask):

    def __init__(
        self,
        name: str = 'port-check',
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        host: str = 'localhost',
        port: Union[int, str] = 80,
        timeout: Union[int, str] = 5,
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
        self._host = host
        self._port = port
        self._timeout = timeout
        self._show_error_interval = show_error_interval

    def copy(self) -> TPortChecker:
        return super().copy()

    def to_function(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., bool]:
        return super().to_function(env_prefix, raise_error)

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        host = self.render_str(self._host)
        port = self.render_int(self._port)
        timeout = self.render_int(self._timeout)
        wait_time = 0
        while not self._check_port(
            host=host,
            port=port,
            timeout=timeout,
            should_print_error=wait_time >= self._show_error_interval
        ):
            if wait_time >= self._show_error_interval:
                wait_time = 0
            await asyncio.sleep(self._checking_interval)
            wait_time += self._checking_interval
        return True

    def _check_port(
        self, host: str, port: int, timeout: int, should_print_error: bool
    ) -> bool:
        label = self._get_label(host, port)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((host, port))
                if result == 0:
                    self.print_out(f'{label} (OK)')
                    return True
                self._debug_and_print_error(
                    f'{label} (Not OK)', should_print_error
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

    def _get_label(self, host: str, port: int) -> str:
        return f'Checking {host}:{port}'

    def __repr__(self) -> str:
        return f'<PortChecker name={self._name}>'
