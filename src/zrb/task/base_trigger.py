import asyncio
from collections.abc import Callable
from typing import Any

from zrb.attr.type import fstring
from zrb.callback.any_callback import AnyCallback
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.context.shared_context import SharedContext
from zrb.dot_dict.dot_dict import DotDict
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.cli.style import CYAN
from zrb.xcom.xcom import Xcom


class BaseTrigger(BaseTask):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: list[AnyInput | None] | AnyInput | None = None,
        env: list[AnyEnv | None] | AnyEnv | None = None,
        action: fstring | Callable[[AnyContext], Any] | None = None,
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
            color=color if color is not None else CYAN,
            icon=icon if icon is not None else "✨",
            description=description,
            cli_only=cli_only,
            input=input,
            env=env,
            action=action,
            execute_condition=execute_condition,
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
        self._callbacks = callback
        self._queue_name = queue_name

    @property
    def queue_name(self) -> str:
        if self._queue_name is None:
            return f"{self.name}"
        return self._queue_name

    @property
    def readiness_checks(self) -> list[AnyTask]:
        readiness_checks = super().readiness_checks
        if len(readiness_checks) > 0:
            return readiness_checks
        return [BaseTask(name=f"{self.name}-check", action=lambda _: True)]

    @property
    def callbacks(self) -> list[AnyCallback]:
        if isinstance(self._callbacks, AnyCallback):
            return [self._callbacks]
        return self._callbacks

    async def exec_root_tasks(self, session: AnySession):
        exchange_xcom = self.get_exchange_xcom(session)
        exchange_xcom.add_push_callback(lambda: self._exchange_push_callback(session))
        return await super().exec_root_tasks(session)

    def _exchange_push_callback(self, session: AnySession):
        coro = asyncio.create_task(self._fanout_and_trigger_callback(session))
        session.defer_coro(coro)

    async def _fanout_and_trigger_callback(self, session: AnySession):
        exchange_xcom = self.get_exchange_xcom(session)
        data = exchange_xcom.pop()
        coros = []
        for callback in self.callbacks:
            xcom_dict = DotDict({self.queue_name: Xcom([data])})
            callback_session = Session(
                shared_ctx=SharedContext(xcom=xcom_dict),
                parent=session,
                root_group=session.root_group,
            )
            coros.append(asyncio.create_task(callback.async_run(callback_session)))
        await asyncio.gather(*coros)

    def get_exchange_xcom(self, session: AnySession) -> Xcom:
        shared_ctx = session.shared_ctx
        if self.queue_name not in shared_ctx.xcom:
            shared_ctx.xcom[self.queue_name] = Xcom()
        return shared_ctx.xcom[self.queue_name]
