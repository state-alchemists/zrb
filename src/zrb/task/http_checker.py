from typing import Any, Union
from .base_task import BaseTask
from http.client import HTTPConnection, HTTPSConnection

import asyncio


class HTTPChecker(BaseTask):
    name: str = 'http_checker'
    host: str = 'localhost'
    port: Union[int, str]
    timeout: Union[int, str] = 5
    method: str = 'HEAD'
    url: str = '/'
    is_https: bool = False

    async def run(self, **kwargs: Any):
        method = self.render_str(self.method)
        host = self.render_str(self.host)
        port = self.render_int(self.port)
        url = self.render_str(self.url)
        timeout = self.render_int(self.timeout)
        while not self._check_connection(method, host, port, url, timeout):
            await asyncio.sleep(self.checking_interval)

    def _check_connection(
        self, method: str, host: str, port: int, url: str, timeout: int
    ) -> bool:
        label = self._get_label(method, host, port, url)
        conn = self._get_connection(host, port, timeout)
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

    def _get_label(self, method: str, host: str, port: int, url: str) -> str:
        protocol = 'https' if self.is_https else 'http'
        return f'{method} {protocol}://{host}:{port}{url}'

    def _get_connection(
        self, host: str, port: int, timeout: int
    ) -> Union[HTTPConnection, HTTPSConnection]:
        if self.is_https:
            return HTTPSConnection(host, port, timeout=timeout)
        return HTTPConnection(host, port, timeout=timeout)
