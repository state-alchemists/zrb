from collections.abc import Callable

from .any_task import AnyTask
from .base_task import BaseTask
from ..attr.type import StrAttr, IntAttr
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..context.any_context import AnyContext
from ..context.context import Context
from ..util.attr import get_str_attr, get_int_attr
import asyncio


class TcpCheck(BaseTask):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        input: list[AnyInput] | AnyInput | None = None,
        env: list[AnyEnv] | AnyEnv | None = None,
        host: StrAttr = "localhost",
        auto_render_host: bool = True,
        port: IntAttr = 80,
        interval: int = 5,
        execute_condition: bool | str | Callable[[Context], bool] = True,
        upstream: list[AnyTask] | AnyTask | None = None,
        fallback: list[AnyTask] | AnyTask | None = None,
    ):
        super().__init__(
            name=name,
            color=color,
            icon=icon,
            description=description,
            input=input,
            env=env,
            execute_condition=execute_condition,
            retries=0,
            upstream=upstream,
            fallback=fallback,
        )
        self._host = host
        self._auto_render_host = auto_render_host
        self._port = port
        self._interval = interval

    def _get_host(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._host, "localhost", auto_render=self._auto_render_host)

    def _get_port(self, ctx: AnyContext) -> str:
        return get_int_attr(ctx, self._port, 80, auto_render=True)

    async def _exec_action(self, ctx: AnyContext) -> bool:
        host = self._get_host(ctx)
        port = self._get_port(ctx)
        while True:
            try:
                ctx.log_info(f"Checking TCP connection on {host}:{port}")
                await asyncio.open_connection(host, port)
                ctx.log_info(f"Connection to {host}:{port} established successfully")
                return True
            except asyncio.TimeoutError as e:
                ctx.log_info(f"Timeout error {e}")
            except Exception as e:
                ctx.log_info(f"Error: {e}")
            await asyncio.sleep(self._interval)
