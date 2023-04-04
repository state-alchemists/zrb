from typing import Any, Callable, Iterable, Optional, Union
from typeguard import typechecked
from http.client import HTTPConnection, HTTPSConnection
from .base_task import BaseTask, Group
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_input.base_input import BaseInput

import asyncio


@typechecked
class HTTPChecker(BaseTask):

    def __init__(
        self,
        name: str = 'http-check',
        group: Optional[Group] = None,
        inputs: Iterable[BaseInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        host: str = 'localhost',
        port: Union[int, str] = 80,
        timeout: Union[int, str] = 5,
        method: str = 'HEAD',
        url: str = '/',
        is_https: Union[bool, str] = False,
        upstreams: Iterable[BaseTask] = [],
        checking_interval: float = 0.1,
        skip_execution: Union[bool, str] = False,
        show_error_interval: float = 5
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
            skip_execution=skip_execution
        )
        self.host = host
        self.port = port
        self.timeout = timeout
        self.method = method
        self.url = url
        self.is_https = is_https
        self.show_error_interval = show_error_interval

    def create_main_loop(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., bool]:
        return super().create_main_loop(env_prefix, raise_error)

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        is_https = self.render_bool(self.is_https)
        method = self.render_str(self.method)
        host = self.render_str(self.host)
        port = self.render_int(self.port)
        url = self.render_str(self.url)
        timeout = self.render_int(self.timeout)
        wait_time = 0
        while not self._check_connection(
            method=method,
            host=host,
            port=port,
            url=url,
            is_https=is_https,
            timeout=timeout,
            should_print_error=wait_time >= self.show_error_interval
        ):
            if wait_time >= self.show_error_interval:
                wait_time = 0
            await asyncio.sleep(self.checking_interval)
            wait_time += self.checking_interval
        return True

    def _check_connection(
        self,
        method: str,
        host: str,
        port: int,
        url: str,
        is_https: bool,
        timeout: int,
        should_print_error: bool
    ) -> bool:
        label = self._get_label(method, host, port, is_https, url)
        conn = self._get_connection(host, port, is_https, timeout)
        try:
            conn.request(method, url)
            res = conn.getresponse()
            if res.status < 300:
                self.log_info('Connection success')
                self.print_out(f'{label} {res.status} (OK)')
                return True
            self._debug_and_print_error(
                f'{label} {res.status} (Not OK)', should_print_error
            )
        except Exception:
            self._debug_and_print_error(
                f'{label} Connection error', should_print_error
            )
        finally:
            conn.close()
        return False

    def _debug_and_print_error(self, message: str, should_print_error: bool):
        if should_print_error:
            self.print_err(message)
        self.log_debug(message)

    def _get_label(
        self, method: str, host: str, port: int, is_https: bool, url: str
    ) -> str:
        protocol = 'https' if is_https else 'http'
        return f'{method} {protocol}://{host}:{port}{url}'

    def _get_connection(
        self, host: str, port: int, is_https: bool, timeout: int
    ) -> Union[HTTPConnection, HTTPSConnection]:
        if is_https:
            return HTTPSConnection(host, port, timeout=timeout)
        return HTTPConnection(host, port, timeout=timeout)
