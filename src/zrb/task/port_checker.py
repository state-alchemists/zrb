from typing import Any, Union
from .base_task import BaseTask

import socket
import asyncio


class PortChecker(BaseTask):
    name: str = 'port_checker'
    host: str = 'localhost'
    port: Union[int, str]
    timeout: Union[int, str] = 5

    async def run(self, **kwargs: Any):
        host = self.render_str(self.host)
        port = self.render_int(self.port)
        timeout = self.render_int(self.timeout)
        while not self._check_port(host, port, timeout):
            await asyncio.sleep(self.checking_interval)

    def _check_port(
        self, method: str, host: str, port: int, url: str, timeout: int
    ) -> bool:
        label = self._get_label(method, host, port, url)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            if result == 0:
                self.print_out(f'{label} (OK)')
                return True
        self.log_debug(f'{label} (Not OK)')
        return False

    def _get_label(self, host: str, port: int) -> str:
        return f'Checking {host}:{port}'
