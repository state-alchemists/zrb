from zrb.helper.typing import Any, Callable, Iterable, Optional, Union, TypeVar
from zrb.helper.typecheck import typechecked
from http.client import HTTPConnection, HTTPSConnection
from zrb.task.base_task import BaseTask
from zrb.task.any_task import AnyTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

import asyncio

THTTPChecker = TypeVar('THTTPChecker', bound='HTTPChecker')


@typechecked
class HTTPChecker(BaseTask):

    def __init__(
        self,
        name: str = 'http-check',
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
        method: str = 'HEAD',
        url: str = '/',
        is_https: Union[bool, str] = False,
        upstreams: Iterable[AnyTask] = [],
        checking_interval: float = 0.1,
        show_error_interval: float = 5,
        should_execute: Union[bool, str, Callable[..., bool]] = True
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
            should_execute=should_execute
        )
        self._host = host
        self._port = port
        self._timeout = timeout
        self._method = method
        self._url = url
        self._is_https = is_https
        self._show_error_interval = show_error_interval

    def copy(self) -> THTTPChecker:
        return super().copy()

    def to_function(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., bool]:
        return super().to_function(env_prefix, raise_error)

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        is_https = self.render_bool(self._is_https)
        method = self.render_str(self._method)
        host = self.render_str(self._host)
        port = self.render_int(self._port)
        url = self.render_str(self._url)
        if not url.startswith('/'):
            url = '/' + url
        timeout = self.render_int(self._timeout)
        wait_time = 0
        while not self._check_connection(
            method=method,
            host=host,
            port=port,
            url=url,
            is_https=is_https,
            timeout=timeout,
            should_print_error=wait_time >= self._show_error_interval
        ):
            if wait_time >= self._show_error_interval:
                wait_time = 0
            await asyncio.sleep(self._checking_interval)
            wait_time += self._checking_interval
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

    def __repr__(self) -> str:
        return f'<HttpChecker name={self._name}>'
