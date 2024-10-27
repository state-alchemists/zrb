from collections.abc import Callable
from .any_task import AnyTask
from .base_task import BaseTask
from ..attr.type import StrAttr
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..context.any_context import AnyContext
from ..context.context import Context
from ..util.attr import get_str_attr
import asyncio
import requests


class HttpCheck(BaseTask):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        input: list[AnyInput] | AnyInput | None = None,
        env: list[AnyEnv] | AnyEnv | None = None,
        url: StrAttr = "http://localhost",
        auto_render_url: bool = True,
        http_method: StrAttr = "GET",
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
        self._url = url
        self._auto_render_url = auto_render_url
        self._http_method = http_method
        self._interval = interval

    def _get_url(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._url, "http://localhost", auto_render=self._auto_render_url
        )

    def _get_http_method(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._http_method, "GET", auto_render=True).upper()

    async def _exec_action(self, ctx: AnyContext) -> bool:
        url = self._get_url(ctx)
        http_method = self._get_http_method(ctx)
        while True:
            try:
                response = requests.request(http_method, url)
                if response.status_code == 200:
                    return True
                ctx.log_info(f"HTTP Status code: {response.status_code}")
            except asyncio.TimeoutError as e:
                ctx.log_info(f"Timeout error {e}")
            except Exception as e:
                ctx.log_info(f"Error: {e}")
            await asyncio.sleep(self._interval)
