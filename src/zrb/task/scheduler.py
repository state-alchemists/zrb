import asyncio
import datetime
from collections.abc import Callable

from zrb.attr.type import StrAttr, fstring
from zrb.callback.any_callback import AnyCallback
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_trigger import BaseTrigger
from zrb.util.attr import get_str_attr
from zrb.util.cron import match_cron


class Scheduler(BaseTrigger):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: list[AnyInput | None] | AnyInput | None = None,
        env: list[AnyEnv | None] | AnyEnv | None = None,
        schedule: StrAttr = None,
        execute_condition: bool | str | Callable[[AnySharedContext], bool] = True,
        queue_name: fstring | None = None,
        callback: list[AnyCallback] | AnyCallback = [],
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
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
            queue_name=queue_name,
            callback=callback,
            retries=retries,
            retry_period=retry_period,
            readiness_check=readiness_check,
            readiness_check_delay=readiness_check_delay,
            readiness_check_period=readiness_check_period,
            readiness_failure_threshold=readiness_failure_threshold,
            readiness_timeout=readiness_timeout,
            monitor_readiness=monitor_readiness,
            upstream=upstream,
            fallback=fallback,
            successor=successor,
        )
        self._cron_pattern = schedule

    def _get_cron_pattern(self, shared_ctx: AnySharedContext) -> str:
        return get_str_attr(shared_ctx, self._cron_pattern, "@minutely", True)

    async def _exec_action(self, ctx: AnyContext):
        cron_pattern = self._get_cron_pattern(ctx)
        ctx.print(f"Monitoring cron pattern: {cron_pattern}")
        while True:
            now = datetime.datetime.now()
            ctx.print(f"Current time: {now}")
            if match_cron(cron_pattern, now):
                ctx.print(f"Matching {now} with pattern: {cron_pattern}")
                xcom = self.get_exchange_xcom(ctx.session)
                xcom.push(now)
            await asyncio.sleep(60)
