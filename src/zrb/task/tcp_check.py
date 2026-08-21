import asyncio
from collections.abc import Sequence

from zrb.attr.type import BoolAttr, IntAttr, StrAttr
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base.base_task import BaseTask
from zrb.util.attr import get_int_attr, get_str_attr


class TcpCheck(BaseTask):
    def __init__(
        self,
        name: str,
        *,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: Sequence[AnyInput | None] | AnyInput | None = None,
        env: Sequence[AnyEnv | None] | AnyEnv | None = None,
        host: StrAttr = "localhost",
        render_host: bool = True,
        port: IntAttr = 80,
        interval: float | None = None,
        execute_condition: BoolAttr = True,
        upstream: Sequence[AnyTask] | AnyTask | None = None,
        fallback: Sequence[AnyTask] | AnyTask | None = None,
        successor: Sequence[AnyTask] | AnyTask | None = None,
        print_fn: PrintFn | None = None,
    ):
        """Define a task that passes once a TCP port accepts connections.

        Typically used as another task's `readiness_check`.

        Args:
            host: Host to connect to. A template rendered against the context, or
                a callable taking it.
            render_host: Whether to render `host` as a template.
            port: Port to connect to.
            interval: Seconds between attempts. Defaults to the readiness check
                period.

        Every parameter `BaseTask` accepts is also accepted here and behaves
        identically; see `BaseTask` for those.
        """
        super().__init__(
            name=name,
            color=color,
            icon=icon,
            description=description,
            cli_only=cli_only,
            input=input,
            env=env,
            execute_condition=execute_condition,
            retries=0,
            upstream=upstream,
            fallback=fallback,
            successor=successor,
            print_fn=print_fn,
        )
        self._host = host
        self._render_host = render_host
        self._port = port
        self._interval = (
            interval if interval is not None else CFG.TCP_CHECK_INTERVAL / 1000
        )

    def _get_host(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._host, "localhost", auto_render=self._render_host)

    def _get_port(self, ctx: AnyContext) -> int:
        return get_int_attr(ctx, self._port, 80, auto_render=True)

    async def _exec_action(self, ctx: AnyContext) -> bool:
        host = self._get_host(ctx)
        port = self._get_port(ctx)
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
            await asyncio.sleep(self._interval)
