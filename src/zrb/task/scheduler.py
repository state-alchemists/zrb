import asyncio
import datetime
from typing import Unpack

from zrb.attr.type import StrAttr
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.base.params import BaseTriggerParams
from zrb.task.base_trigger import BaseTrigger
from zrb.util.attr import get_str_attr
from zrb.util.cron import match_cron


class Scheduler(BaseTrigger):
    def __init__(
        self,
        name: str,
        *,
        schedule: StrAttr | None = None,
        **kwargs: Unpack[BaseTriggerParams],
    ):
        """Define a task that emits an event on a cron schedule.

        Args:
            schedule: Cron expression describing when to fire. A literal, a
                `Tpl` rendered against the context, or a callable taking it.

        Every parameter `BaseTrigger` accepts is also accepted here and behaves
        identically; see `BaseTrigger` for those.
        """
        super().__init__(
            name=name,
            **kwargs,
        )
        self._cron_pattern = schedule

    def _get_cron_pattern(self, shared_ctx: AnySharedContext) -> str:
        return get_str_attr(shared_ctx, self._cron_pattern, "@minutely")

    async def _exec_action(self, ctx: AnyContext):
        cron_pattern = self._get_cron_pattern(ctx)
        ctx.print(f"Monitoring cron pattern: {cron_pattern}")
        last_fired_minute: datetime.datetime | None = None
        while ctx.session is None or not ctx.session.is_terminated:
            now = datetime.datetime.now()
            ctx.print(f"Current time: {now}")
            minute = now.replace(second=0, microsecond=0)
            # Dedup on the fired minute: a sub-minute tick would otherwise fire
            # several times inside one matching minute.
            if minute != last_fired_minute and match_cron(cron_pattern, now):
                last_fired_minute = minute
                ctx.print(f"Matching {now} with pattern: {cron_pattern}")
                if ctx.session is not None:
                    self.push_exchange_xcom(ctx.session, now)
            # Never sleep past the next minute boundary: an unaligned 60s sleep
            # accumulates loop overhead each tick, and once the sample point
            # drifts across a boundary an entire minute is skipped — a
            # `30 9 * * *` job silently not firing that day.
            tick = CFG.SCHEDULER_TICK_INTERVAL / 1000
            to_next_minute = 60 - now.second - now.microsecond / 1_000_000
            await asyncio.sleep(min(tick, to_next_minute))
