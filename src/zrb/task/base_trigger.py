from collections.abc import Callable
from typing import Any
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from .base_task import BaseTask
from ..attr.type import fstring
from ..callback.any_callback import AnyCallback
from ..dot_dict.dot_dict import DotDict
from ..session.any_session import AnySession
from ..session.session import Session
from ..context.shared_context import SharedContext
from ..xcom.xcom import Xcom
from ..util.cli.style import CYAN

import asyncio


class BaseTrigger(BaseTask):

    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: list[AnyInput] | AnyInput | None = None,
        env: list[AnyEnv] | AnyEnv | None = None,
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
        fallback: list[AnyTask] | AnyTask | None = None
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
        )
        self._callbacks = callback
        self._exchange_queue_name = queue_name
        self._default_readiness_check = None

    @property
    def exchange_queue_name(self) -> str:
        if self._exchange_queue_name is None:
            return f"exchange-{self.name}"
        return self._exchange_queue_name

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
            xcom_dict = DotDict({callback.queue_name: Xcom([data])})
            callback_session = Session(
                shared_ctx=SharedContext(xcom=xcom_dict), parent=session
            )
            coros.append(asyncio.create_task(callback.async_run(callback_session)))
        await asyncio.gather(*coros)

    def get_exchange_xcom(self, session: AnySession) -> Xcom:
        shared_ctx = session.shared_ctx
        if self.exchange_queue_name not in shared_ctx.xcom:
            shared_ctx.xcom[self.exchange_queue_name] = Xcom()
        return shared_ctx.xcom[self.exchange_queue_name]
