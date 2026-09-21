import asyncio
from typing import Unpack

from zrb.attr.type import IntAttr, StrAttr
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.task.base.base_task import BaseTask
from zrb.task.base.params import CheckTaskParams, reject_non_check_params
from zrb.util.attr import get_int_attr, get_str_attr


class TcpCheck(BaseTask):
    def __init__(
        self,
        name: str,
        *,
        host: StrAttr = "localhost",
        port: IntAttr = 80,
        interval: float | None = None,
        **kwargs: Unpack[CheckTaskParams],
    ):
        """Define a task that passes once a TCP port accepts connections.

        Typically used as another task's `readiness_check`.

        Args:
            host: Host to connect to. A literal, a `Tpl` rendered against the
                context, or a callable taking it.
            port: Port to connect to.
            interval: Seconds between attempts. Defaults to the readiness check
                period.

        Every parameter `BaseTask` accepts is also accepted here **except the
        retry and readiness settings** (`retries`, `retry_period`, `retry_if`,
        `readiness_*`, `monitor_readiness`): a check polls on its own
        `interval` and is itself what a task waits on, so those would nest a
        check inside itself. Set them on the task being checked.
        """
        reject_non_check_params("TcpCheck", dict(kwargs))
        super().__init__(
            name=name,
            **kwargs,
            retries=0,
        )
        self._host = host
        self._port = port
        # Read lazily at run time (like every other CFG read) so an env change
        # after task definition still takes effect.
        self._interval = interval

    def _get_interval(self) -> float:
        if self._interval is not None:
            return self._interval
        return CFG.TCP_CHECK_INTERVAL / 1000

    def _get_host(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._host, "localhost")

    def _get_port(self, ctx: AnyContext) -> int:
        return get_int_attr(ctx, self._port, 80)

    async def _exec_action(self, ctx: AnyContext) -> bool:
        host = self._get_host(ctx)
        port = self._get_port(ctx)
        interval = self._get_interval()
        while True:
            try:
                ctx.log_info(f"Checking TCP connection on {host}:{port}")
                _, writer = await asyncio.open_connection(host, port)
                # The successful connection is the readiness signal. Close the
                # writer to avoid leaking the socket, but a cleanup error must not
                # flip success back into a retry.
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as close_error:
                    ctx.log_info(f"Error closing probe connection: {close_error}")
                ctx.log_info(f"Connection to {host}:{port} established successfully")
                return True
            except asyncio.TimeoutError as e:
                ctx.log_info(f"Timeout error {e}")
            except Exception as e:
                ctx.log_info(f"Error: {e}")
            await asyncio.sleep(interval)
