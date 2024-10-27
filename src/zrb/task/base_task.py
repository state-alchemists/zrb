from typing import Any
from collections.abc import Callable
from ..attr.type import BoolAttr
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..context.shared_context import AnySharedContext
from ..context.shared_context import SharedContext
from ..context.any_context import AnyContext
from ..session.any_session import AnySession
from ..session.session import Session
from ..util.attr import get_bool_attr
from ..util.run import run_async
from ..xcom.xcom import Xcom
from .any_task import AnyTask

import asyncio
import os


class BaseTask(AnyTask):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        input: list[AnyInput] | AnyInput | None = None,
        env: list[AnyEnv] | AnyEnv | None = None,
        action: str | Callable[[AnyContext], Any] | None = None,
        execute_condition: BoolAttr = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
        upstream: list[AnyTask] | AnyTask | None = None,
        fallback: list[AnyTask] | AnyTask | None = None,
    ):
        self._name = name
        self._color = color
        self._icon = icon
        self._description = description
        self._inputs = input
        self._envs = env
        self._retries = retries
        self._retry_period = retry_period
        self._upstreams = upstream
        self._fallbacks = fallback
        self._readiness_checks = readiness_check
        self._readiness_check_period = readiness_check_period
        self._readiness_failure_threshold = readiness_failure_threshold
        self._readiness_timeout = readiness_timeout
        self._monitor_readiness = monitor_readiness
        self._execute_condition = execute_condition
        self._action = action

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self._name}>"

    def __rshift__(self, other: AnyTask | list[AnyTask]) -> AnyTask:
        if isinstance(other, AnyTask):
            other.set_upstreams(self)
        elif isinstance(other, list):
            for task in other:
                task.set_upstreams(self)
        return other

    def __lshift__(self, other: AnyTask | list[AnyTask]) -> AnyTask:
        self.set_upstreams(other)
        return self

    def get_name(self) -> str:
        return self._name

    def get_color(self) -> int | None:
        return self._color

    def get_icon(self) -> str | None:
        return self._icon

    def get_description(self) -> str:
        return self._description if self._description is not None else self.get_name()

    def get_envs(self) -> list[AnyEnv]:
        envs = []
        for upstream in self.get_upstreams():
            envs += upstream.get_envs()
        if isinstance(self._envs, AnyEnv):
            envs.append(self._envs)
        elif self._envs is not None:
            envs += self._envs
        return envs

    def get_inputs(self) -> list[AnyInput]:
        inputs = []
        for upstream in self.get_upstreams():
            inputs += upstream.get_inputs()
        if isinstance(self._inputs, AnyInput):
            inputs.append(self._inputs)
        elif self._inputs is not None:
            inputs += self._inputs
        return inputs

    def get_fallbacks(self) -> list[AnyTask]:
        if self._fallbacks is None:
            return []
        elif isinstance(self._fallbacks, AnyTask):
            return [self._fallbacks]
        return self._fallbacks

    def get_upstreams(self) -> list[AnyTask]:
        if self._upstreams is None:
            return []
        elif isinstance(self._upstreams, AnyTask):
            return [self._upstreams]
        return self._upstreams

    def set_upstreams(self, upstreams: AnyTask | list[AnyTask]):
        if self._upstreams is None:
            self._upstreams = []
        if isinstance(upstreams, AnyTask):
            self._upstreams.append(upstreams)
            return
        self._upstreams += upstreams

    def get_readiness_checks(self) -> list[AnyTask]:
        if self._readiness_checks is None:
            return []
        elif isinstance(self._readiness_checks, AnyTask):
            return [self._readiness_checks]
        return self._readiness_checks

    def run(self, shared_context: AnySharedContext | None = None) -> Any:
        try:
            return asyncio.run(self.async_run(shared_context))
        except KeyboardInterrupt:
            pass

    async def async_run(self, shared_context: AnySharedContext | None = None) -> Any:
        if shared_context is None:
            shared_context = SharedContext()
        # Update session
        self._fill_shared_context_inputs(shared_context)
        self._fill_shared_context_envs(shared_context)
        # Create state
        session = Session(shared_context=shared_context)
        try:
            return await run_async(self.exec_root_tasks(session))
        except KeyboardInterrupt:
            ctx = session.get_ctx(self)
            ctx.log_info("Terminating sesion because of keyboard interrupt")
            session.terminate()
        finally:
            ctx = session.get_ctx(self)
            ctx.log_debug(session)

    def _fill_shared_context_envs(self, shared_context: AnySharedContext):
        # Inject os environ
        os_env_map = {
            key: val for key, val in os.environ.items()
            if key not in shared_context._env
        }
        shared_context._env.update(os_env_map)
        # Inject environment from task's envs
        for env in self.get_envs():
            env.update_shared_context(shared_context)

    def _fill_shared_context_inputs(self, shared_context: AnySharedContext):
        for task_input in self.get_inputs():
            if task_input.get_name() not in shared_context._input:
                task_input.update_shared_context(shared_context)

    async def exec_root_tasks(self, session: AnySession):
        session.register_task(self)
        root_tasks = [
            task for task in session.get_root_tasks(self) if session.is_allowed_to_run(task)
        ]
        root_task_coros = [
            run_async(root_task.exec_chain(session)) for root_task in root_tasks
        ]
        await asyncio.gather(*root_task_coros)
        await session.wait_deferred_monitoring()
        await session.wait_deferred_action()
        xcom: Xcom = session.get_ctx(self).xcom.get(self.get_name())
        return xcom.peek_value()

    async def exec_chain(self, session: AnySession):
        if session.is_terminated or not session.is_allowed_to_run(self):
            return
        result = await self.exec(session)
        # Get next tasks
        nexts = session.get_next_tasks(self)
        if session.is_terminated or len(nexts) == 0:
            return result
        # Run next tasks asynchronously
        next_coros = [
            run_async(next.exec_chain(session)) for next in nexts
        ]
        return await asyncio.gather(*next_coros)

    async def exec(self, session: AnySession):
        ctx = session.get_ctx(self)
        if not session.is_allowed_to_run(self):
            # Task is not allowed to run, skip it for now.
            # This will be triggered later
            ctx.log_info("Not allowed to run")
            return
        if not self._get_execute_condition(session):
            # Skip the task
            ctx.log_info("Marked as skipped")
            session.get_task_status(self).mark_as_skipped()
            return
        # Wait for task to be ready
        await run_async(self._exec_action_until_ready(session))

    def _get_execute_condition(self, session: Session) -> bool:
        ctx = session.get_ctx(self)
        return get_bool_attr(ctx, self._execute_condition, True, auto_render=True)

    async def _exec_action_until_ready(self, session: AnySession):
        ctx = session.get_ctx(self)
        readiness_checks = self.get_readiness_checks()
        if len(readiness_checks) == 0:
            ctx.log_info("No readiness checks")
            # Task has no readiness check
            result = await run_async(self._exec_action_and_retry(session))
            ctx.log_info("Marked as ready")
            session.get_task_status(self).mark_as_ready()
            return result
        # Start the task along with the readiness checks
        action_coro = asyncio.create_task(run_async(self._exec_action_and_retry(session)))
        readiness_check_coros = [
            run_async(check.exec_chain(session))
            for check in readiness_checks
        ]
        # Only wait for readiness checks and mark the task as ready
        ctx.log_info("Start readiness checks")
        result = await asyncio.gather(*readiness_check_coros)
        ctx.log_info("Readiness checks completed")
        ctx.log_info("Marked as ready")
        session.get_task_status(self).mark_as_ready()
        # Defer task's coroutines, will be waited later
        session.defer_action(self, action_coro)
        if self._monitor_readiness:
            monitor_and_rerun_coro = asyncio.create_task(
                run_async(self._exec_monitoring(session, action_coro))
            )
            session.defer_monitoring(self, monitor_and_rerun_coro)
        return result

    async def _exec_monitoring(self, session: AnySession, action_coro: asyncio.Task):
        readiness_checks = self.get_readiness_checks()
        failure_count = 0
        ctx = session.get_ctx(self)
        while not session.is_terminated:
            await asyncio.sleep(self._readiness_check_period)
            if failure_count < self._readiness_failure_threshold:
                for readiness_check in readiness_checks:
                    session.get_task_status(readiness_check).reset_history()
                    session.get_task_status(readiness_check).reset()
                    readiness_xcom: Xcom = ctx.xcom[self.get_name()]
                    readiness_xcom.clear()
                readiness_check_coros = [
                    check.exec_chain(session) for check in readiness_checks
                ]
                try:
                    ctx.log_info("Checking")
                    await asyncio.wait_for(
                        asyncio.gather(*readiness_check_coros), timeout=self._readiness_timeout
                    )
                    ctx.log_info("OK")
                    continue
                except (asyncio.CancelledError, KeyboardInterrupt):
                    for readiness_check in readiness_checks:
                        ctx.log_info("Marked as failed")
                        session.get_task_status(readiness_check).mark_as_failed()
                except asyncio.TimeoutError:
                    failure_count += 1
                    ctx.log_info("Detecting failure")
                    ctx.log_debug(f"Failure count: {failure_count}")
            # Readiness check failed, reset
            ctx.log_info("Resetting")
            action_coro.cancel()
            session.get_task_status(self).reset()
            # defer this action
            ctx.log_info("Running")
            action_coro = asyncio.create_task(run_async(self._exec_action_and_retry(session)))
            session.defer_action(self, action_coro)
            failure_count = 0
            ctx.log_info("Continue monitoring")

    async def _exec_action_and_retry(self, session: AnySession) -> Any:
        ctx = session.get_ctx(self)
        max_attempt = self._retries + 1
        ctx.set_max_attempt(max_attempt)
        for attempt in range(max_attempt):
            ctx.set_attempt(attempt + 1)
            if attempt > 0:
                # apply retry period only if this is not the first attempt
                await asyncio.sleep(self._retry_period)
            try:
                ctx.log_info("Marked as started")
                session.get_task_status(self).mark_as_started()
                result = await run_async(self._exec_action(ctx))
                ctx.log_info("Marked as completed")
                session.get_task_status(self).mark_as_completed()
                # Put result on xcom
                task_xcom: Xcom = ctx.xcom.get(self.get_name())
                task_xcom.push_value(result)
                return result
            except (asyncio.CancelledError, KeyboardInterrupt):
                ctx.log_info("Marked as failed")
                session.get_task_status(self).mark_as_failed()
                return
            except Exception as e:
                ctx.log_error(e)
                if attempt < max_attempt - 1:
                    ctx.log_info("Marked as failed")
                    session.get_task_status(self).mark_as_failed()
                    continue
                ctx.log_info("Marked as permanently failed")
                session.get_task_status(self).mark_as_permanently_failed()
                await run_async(self._exec_fallbacks(session))
                raise e

    async def _exec_fallbacks(self, session: AnySession) -> Any:
        fallbacks: list[AnyTask] = self.get_fallbacks()
        fallback_coros = [
            run_async(fallback.exec_chain(session)) for fallback in fallbacks
        ]
        await asyncio.gather(*fallback_coros)

    async def _exec_action(self, ctx: AnyContext) -> Any:
        """Execute the main action of the task.
        By default will render and run the _action attribute.

        Override this method to define custom action.

        Args:
            session (AnySession): The shared session.

        Returns:
            Any: The result of the action execution.
        """
        if self._action is None:
            return
        if isinstance(self._action, str):
            return ctx.render(self._action)
        return await run_async(self._action(ctx))
