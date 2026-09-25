import asyncio
from typing import TYPE_CHECKING, Unpack

from zrb.attr.type import StrAttr
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.task.base.base_task import BaseTask
from zrb.task.base.params import CheckTaskParams, reject_non_check_params
from zrb.util.attr import get_str_attr

if TYPE_CHECKING:
    from requests import Response


class HttpCheck(BaseTask):
    def __init__(
        self,
        name: str,
        *,
        url: StrAttr = "http://localhost",
        http_method: StrAttr = "GET",
        interval: float | None = None,
        **kwargs: Unpack[CheckTaskParams],
    ):
        """Define a task that passes once an HTTP endpoint responds.

        Typically used as another task's `readiness_check`.

        Args:
            url: URL to poll. A literal, a `Tpl` rendered against the context,
                or a callable taking it.
            http_method: HTTP method to send.
            interval: Seconds between polls. Defaults to
                `CFG.HTTP_CHECK_INTERVAL`.

        Every parameter `BaseTask` accepts is also accepted here **except the
        retry and readiness settings** (`retries`, `retry_period`, `retry_if`,
        `readiness_*`, `monitor_readiness`): a check polls on its own
        `interval` and is itself what a task waits on, so those would nest a
        check inside itself. Set them on the task being checked.
        """
        reject_non_check_params("HttpCheck", dict(kwargs))
        super().__init__(
            name=name,
            **kwargs,
            retries=0,
        )
        self._url = url
        self._http_method = http_method
        # None resolves CFG at run time, so a later env change takes effect.
        self._interval = interval

    def _get_interval(self) -> float:
        if self._interval is not None:
            return self._interval
        return CFG.HTTP_CHECK_INTERVAL / 1000

    def _get_url(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._url, "http://localhost")

    def _get_http_method(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._http_method, "GET").upper()

    async def _exec_action(self, ctx: AnyContext) -> "Response":
        import requests  # lazy: heavy third-party

        url = self._get_url(ctx)
        http_method = self._get_http_method(ctx)
        interval = self._get_interval()
        while True:
            try:
                # to_thread cannot cancel a blocking request, so bound each probe
                # by the interval; a timeout is retried like any other error.
                response = await asyncio.to_thread(
                    requests.request, http_method, url, timeout=interval
                )
                if response.status_code == 200:
                    return response
                ctx.log_info(f"HTTP Status code: {response.status_code}")
            except Exception as e:
                ctx.log_info(f"Error: {e}")
            await asyncio.sleep(interval)
