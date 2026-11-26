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
from zrb.util.cron import match_cron, validate_cron_expression


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
                A literal is validated here; a rendered one when it is first
                used, since its text is not known before then.

        Raises:
            ValueError: If `schedule` is not a usable cron expression or
                shortcut.

        Every other parameter is `BaseTrigger`'s.
        """
        super().__init__(
            name=name,
            **kwargs,
        )
        if isinstance(schedule, str):
            validate_cron_expression(schedule)
        self._cron_pattern = schedule

    def _get_cron_pattern(self, shared_ctx: AnySharedContext) -> str:
        cron_pattern = get_str_attr(shared_ctx, self._cron_pattern, "@minutely")
        # A rendered pattern matches nothing at all when it is wrong, so the
        # scheduler would print "Monitoring" and never fire.
        validate_cron_expression(cron_pattern)
        return cron_pattern

    async def _exec_action(self, ctx: AnyContext):
        cron_pattern = self._get_cron_pattern(ctx)
        ctx.print(f"Monitoring cron pattern: {cron_pattern}")
        last_fired_minute: datetime.datetime | None = None
        while ctx.session is None or not ctx.session.is_terminated:
            now = datetime.datetime.now()
            ctx.print(f"Current time: {now}")
            minute = now.replace(second=0, microsecond=0)
            # A sub-minute tick must fire once per matching minute.
            if minute != last_fired_minute and match_cron(cron_pattern, now):
                last_fired_minute = minute
                ctx.print(f"Matching {now} with pattern: {cron_pattern}")
                if ctx.session is not None:
                    self.push_exchange_xcom(ctx.session, now)
            # Never sleep past the next minute boundary, or drift can skip a
            # matching minute entirely.
            tick = CFG.SCHEDULER_TICK_INTERVAL / 1000
            to_next_minute = 60 - now.second - now.microsecond / 1_000_000
            await asyncio.sleep(min(tick, to_next_minute))
