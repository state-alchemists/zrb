import asyncio
from collections.abc import Callable

from zrb.attr.type import StrAttr
from zrb.context.any_context import AnyContext
from zrb.context.context import Context
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_str_attr


class HttpCheck(BaseTask):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: list[AnyInput] | AnyInput | None = None,
        env: list[AnyEnv] | AnyEnv | None = None,
        url: StrAttr = "http://localhost",
        render_url: bool = True,
        http_method: StrAttr = "GET",
        interval: int = 5,
        execute_condition: bool | str | Callable[[Context], bool] = True,
        upstream: list[AnyTask] | AnyTask | None = None,
        fallback: list[AnyTask] | AnyTask | None = None,
        successor: list[AnyTask] | AnyTask | None = None,
    ):
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
        )
        self._url = url
        self._render_url = render_url
        self._http_method = http_method
        self._interval = interval

    def _get_url(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._url, "http://localhost", auto_render=self._render_url
        )

    def _get_http_method(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._http_method, "GET", auto_render=True).upper()

    async def _exec_action(self, ctx: AnyContext) -> bool:
        import requests

        url = self._get_url(ctx)
        http_method = self._get_http_method(ctx)
        while True:
            try:
                response = requests.request(http_method, url)
                if response.status_code == 200:
                    return response
                ctx.log_info(f"HTTP Status code: {response.status_code}")
            except asyncio.TimeoutError as e:
                ctx.log_info(f"Timeout error {e}")
            except Exception as e:
                ctx.log_info(f"Error: {e}")
            await asyncio.sleep(self._interval)
