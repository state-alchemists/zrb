import asyncio
from typing import Any, Unpack

from zrb.callback.any_callback import AnyCallback
from zrb.context.shared_context import SharedContext
from zrb.dot_dict.dot_dict import DotDict
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.task.base.base_task import BaseTask
from zrb.task.base.params import ActionTaskParams
from zrb.util.cli.style import CYAN
from zrb.xcom.xcom import Xcom


class BaseTrigger(BaseTask):
    """A `BaseTask` that fires callbacks when data lands on its XCom queue —
    the base for `Scheduler` and other event-driven tasks."""

    def __init__(
        self,
        name: str,
        *,
        queue_name: str | None = None,
        callback: list[AnyCallback] | AnyCallback | None = None,
        **kwargs: Unpack[ActionTaskParams],
    ):
        """Define a trigger. Every parameter besides `queue_name` and
        `callback` is `BaseTask`'s, with the same meaning; `color` and `icon`
        default to a distinct cyan `✨` instead of `BaseTask`'s.

        Args:
            queue_name: Name of the XCom queue callbacks watch — adding data
                to `xcom[queue_name]` fires them. Read through the
                `queue_name` property, which has no context, so it is a plain
                `str`; build it eagerly if it needs to vary.
            callback: Callback(s) run after the trigger action, once data is
                on the queue.
        """
        if kwargs.get("color") is None:
            kwargs["color"] = CYAN
        if kwargs.get("icon") is None:
            kwargs["icon"] = "✨"
        super().__init__(
            name=name,
            **kwargs,
        )
        self._callbacks = callback if callback is not None else []
        self._queue_name = queue_name
        self._default_readiness_check: AnyTask | None = None

    @property
    def queue_name(self) -> str:
        """Name of the xcom queue carrying this trigger's events, defaulting to its name."""
        if self._queue_name is None:
            return f"{self.name}"
        return self._queue_name

    @property
    def readiness_checks(self) -> list[AnyTask]:
        readiness_checks = super().readiness_checks
        if len(readiness_checks) > 0:
            return readiness_checks
        if self._default_readiness_check is None:
            self._default_readiness_check = BaseTask(
                name=f"{self.name}-check", action=lambda _: True
            )
        return [self._default_readiness_check]

    @property
    def callbacks(self) -> list[AnyCallback]:
        """Callbacks invoked once per triggered event, always as a list."""
        if isinstance(self._callbacks, AnyCallback):
            return [self._callbacks]
        return self._callbacks

    async def exec_root_tasks(self, session: AnySession):
        exchange_xcom = self._get_exchange_xcom(session)
        exchange_xcom.append_push_callback(
            lambda: self._exchange_push_callback(session)
        )
        return await super().exec_root_tasks(session)

    def _exchange_push_callback(self, session: AnySession):
        coro = asyncio.create_task(self._fanout_and_trigger_callback(session))
        session.defer_coro(coro)

    async def _fanout_and_trigger_callback(self, session: AnySession):
        data = self.pop_exchange_xcom(session)
        coros = []
        for callback in self.callbacks:
            xcom_dict = DotDict({self.queue_name: Xcom([data])})
            callback_session = Session(
                shared_ctx=SharedContext(
                    input=dict(session.shared_ctx.input),
                    xcom=xcom_dict,
                    print_fn=self._print_fn,
                ),
                parent=session,
                root_group=session.root_group,
            )
            coros.append(
                asyncio.create_task(
                    callback.async_run(parent_session=session, session=callback_session)
                )
            )
        # Fail-fast fan-out: a broken callback should surface immediately, not
        # be masked by return_exceptions.
        await asyncio.gather(*coros)

    def _get_exchange_xcom(self, session: AnySession) -> Xcom:
        shared_ctx = session.shared_ctx
        if self.queue_name not in shared_ctx.xcom:
            shared_ctx.xcom[self.queue_name] = Xcom()
        return shared_ctx.xcom[self.queue_name]

    def push_exchange_xcom(self, session: AnySession, data: Any):
        """Publish an event, waking whatever this trigger drives.

        Call this from a trigger implementation when the external condition it
        watches fires.
        """
        exchange_xcom = self._get_exchange_xcom(session)
        exchange_xcom.push(data)

    def pop_exchange_xcom(self, session: AnySession) -> Any:
        """Remove and return the oldest pending event.

        Raises:
            IndexError: If no event is pending.
        """
        exchange_xcom = self._get_exchange_xcom(session)
        return exchange_xcom.pop()
