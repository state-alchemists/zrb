from typing import Any, Callable, Iterable, Optional, Union
from typeguard import typechecked
from http.client import HTTPConnection, HTTPSConnection
from .base_task import BaseTask
from ..task_env.env import Env
from ..task_group.group import Group
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
    ):
        BaseTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            icon=icon,
            color=color,
            description=description,
            upstreams=upstreams,
            checkers=[],
            checking_interval=checking_interval,
            retry=0,
            retry_interval=0
        )
        self.host = host
        self.port = port
        self.timeout = timeout
        self.method = method
        self.url = url
        self.is_https = is_https

    def create_main_loop(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., bool]:
        return super().create_main_loop(env_prefix, raise_error)

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        is_https = self.get_bool(self.is_https)
        method = self.render_str(self.method)
        host = self.render_str(self.host)
        port = self.get_int(self.port)
        url = self.render_str(self.url)
        timeout = self.get_int(self.timeout)
        while not self._check_connection(
            method, host, port, url, is_https, timeout
        ):
            await asyncio.sleep(self.checking_interval)
        return True

    def _check_connection(
        self,
        method: str,
        host: str,
        port: int,
        url: str,
        is_https: bool,
        timeout: int
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
            self.log_debug(f'{label} {res.status} (Not OK)')
        except Exception:
            self.log_debug(f'{label} Connection error')
        finally:
            conn.close()
        return False

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
