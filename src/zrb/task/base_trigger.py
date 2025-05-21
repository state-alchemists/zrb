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
    """
    A base class for tasks that act as triggers or schedulers.

    It extends BaseTask and adds functionality for handling callbacks
    and managing a queue for data exchange.
    """

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
        """
        Initializes a new instance of the BaseTrigger class.

        Args:
            name: The name of the trigger task.
            color: The color to use for the task in the CLI output.
            icon: The icon to display for the task.
            description: A brief description of the task.
            cli_only: If True, the task is only available in the CLI.
            input: The input definition for the task.
            env: The environment variable definition for the task.
            action: The action to be performed by the task.
            execute_condition: A condition that must be met for the task to execute.
            queue_name: The name of the XCom queue used for data
                exchange with callbacks. Whenever any data is added
                to xcom[queue_name], the callback will be triggered.
            callback: A single or list of callbacks to be executed after the trigger action.
            retries: The number of times to retry the task on failure.
            retry_period: The time to wait between retries.
            readiness_check: A single or list of tasks to check for readiness before execution.
            readiness_check_delay: The initial delay before starting
                readiness checks.
            readiness_check_period: The time to wait between readiness checks.
            readiness_failure_threshold: The number of consecutive readiness
                check failures before the task fails.
            readiness_timeout: The maximum time to wait for readiness checks to pass.
            monitor_readiness: If True, monitor readiness checks during execution.
            upstream: A single or list of tasks that must complete before this task starts.
            fallback: A single or list of tasks to run if this task fails.
            successor: A single or list of tasks to run after this task completes successfully.
        """
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
                shared_ctx=SharedContext(
                    input=dict(session.shared_ctx.input),
                    xcom=xcom_dict,
                ),
                parent=session,
                root_group=session.root_group,
            )
            coros.append(
                asyncio.create_task(
                    callback.async_run(parent_session=session, session=callback_session)
                )
            )
        await asyncio.gather(*coros)

    def get_exchange_xcom(self, session: AnySession) -> Xcom:
        shared_ctx = session.shared_ctx
        if self.queue_name not in shared_ctx.xcom:
            shared_ctx.xcom[self.queue_name] = Xcom()
        return shared_ctx.xcom[self.queue_name]
