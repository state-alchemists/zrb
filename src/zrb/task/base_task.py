import asyncio
import os
from collections.abc import Callable, Coroutine
from typing import Any

from zrb.attr.type import BoolAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.context.shared_context import AnySharedContext, SharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.util.attr import get_bool_attr
from zrb.util.run import run_async
from zrb.xcom.xcom import Xcom


class BaseTask(AnyTask):
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
        execute_condition: BoolAttr = True,
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
        self._name = name
        self._color = color
        self._icon = icon
        self._description = description
        self._cli_only = cli_only
        self._inputs = input
        self._envs = env
        self._retries = retries
        self._retry_period = retry_period
        self._upstreams = upstream
        self._fallbacks = fallback
        self._successors = successor
        self._readiness_checks = readiness_check
        self._readiness_check_delay = readiness_check_delay
        self._readiness_check_period = readiness_check_period
        self._readiness_failure_threshold = readiness_failure_threshold
        self._readiness_timeout = readiness_timeout
        self._monitor_readiness = monitor_readiness
        self._execute_condition = execute_condition
        self._action = action

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self._name}>"

    def __rshift__(self, other: AnyTask | list[AnyTask]) -> AnyTask | list[AnyTask]:
        try:
            if isinstance(other, AnyTask):
                other.append_upstream(self)
            elif isinstance(other, list):
                for task in other:
                    task.append_upstream(self)
            return other
        except Exception as e:
            raise ValueError(f"Invalid operation {self} >> {other}: {e}")

    def __lshift__(self, other: AnyTask | list[AnyTask]) -> AnyTask:
        try:
            self.append_upstream(other)
            return self
        except Exception as e:
            raise ValueError(f"Invalid operation {self} << {other}: {e}")

    @property
    def name(self) -> str:
        return self._name

    @property
    def color(self) -> int | None:
        return self._color

    @property
    def icon(self) -> str | None:
        return self._icon

    @property
    def description(self) -> str:
        return self._description if self._description is not None else self.name

    @property
    def cli_only(self) -> bool:
        return self._cli_only

    @property
    def envs(self) -> list[AnyEnv]:
        envs = []
        for upstream in self.upstreams:
            envs += upstream.envs
        if isinstance(self._envs, AnyEnv):
            envs.append(self._envs)
        elif self._envs is not None:
            envs += self._envs
        return [env for env in envs if env is not None]

    @property
    def inputs(self) -> list[AnyInput]:
        inputs = []
        for upstream in self.upstreams:
            self.__combine_inputs(inputs, upstream.inputs)
        if self._inputs is not None:
            self.__combine_inputs(inputs, self._inputs)
        return [task_input for task_input in inputs if task_input is not None]

    def __combine_inputs(
        self,
        inputs: list[AnyInput],
        other_inputs: list[AnyInput | None] | AnyInput | None,
    ):
        input_names = [task_input.name for task_input in inputs]
        if isinstance(other_inputs, AnyInput):
            other_inputs = [other_inputs]
        elif other_inputs is None:
            other_inputs = []
        for task_input in other_inputs:
            if task_input is None:
                continue
            if task_input.name not in input_names:
                inputs.append(task_input)

    @property
    def fallbacks(self) -> list[AnyTask]:
        if self._fallbacks is None:
            return []
        elif isinstance(self._fallbacks, AnyTask):
            return [self._fallbacks]
        return self._fallbacks

    def append_fallback(self, fallbacks: AnyTask | list[AnyTask]):
        fallback_list = [fallbacks] if isinstance(fallbacks, AnyTask) else fallbacks
        for fallback in fallback_list:
            self.__append_fallback(fallback)

    def __append_fallback(self, fallback: AnyTask):
        # Make sure self._fallbacks is a list
        if self._fallbacks is None:
            self._fallbacks = []
        elif isinstance(self._fallbacks, AnyTask):
            self._fallbacks = [self._fallbacks]
        # Add fallback if it was not on self._fallbacks
        if fallback not in self._fallbacks:
            self._fallbacks.append(fallback)

    @property
    def successors(self) -> list[AnyTask]:
        if self._successors is None:
            return []
        elif isinstance(self._successors, AnyTask):
            return [self._successors]
        return self._successors

    def append_successor(self, successors: AnyTask | list[AnyTask]):
        successor_list = [successors] if isinstance(successors, AnyTask) else successors
        for successor in successor_list:
            self.__append_successor(successor)

    def __append_successor(self, successor: AnyTask):
        # Make sure self._successors is a list
        if self._successors is None:
            self._successors = []
        elif isinstance(self._successors, AnyTask):
            self._successors = [self._successors]
        # Add successor if it was not on self._successors
        if successor not in self._successors:
            self._successors.append(successor)

    @property
    def readiness_checks(self) -> list[AnyTask]:
        if self._readiness_checks is None:
            return []
        elif isinstance(self._readiness_checks, AnyTask):
            return [self._readiness_checks]
        return self._readiness_checks

    def append_readiness_check(self, readiness_checks: AnyTask | list[AnyTask]):
        readiness_check_list = (
            [readiness_checks]
            if isinstance(readiness_checks, AnyTask)
            else readiness_checks
        )
        for readiness_check in readiness_check_list:
            self.__append_readiness_check(readiness_check)

    def __append_readiness_check(self, readiness_check: AnyTask):
        # Make sure self._readiness_checks is a list
        if self._readiness_checks is None:
            self._readiness_checks = []
        elif isinstance(self._readiness_checks, AnyTask):
            self._readiness_checks = [self._readiness_checks]
        # Add readiness_check if it was not on self._readiness_checks
        if readiness_check not in self._readiness_checks:
            self._readiness_checks.append(readiness_check)

    @property
    def upstreams(self) -> list[AnyTask]:
        if self._upstreams is None:
            return []
        elif isinstance(self._upstreams, AnyTask):
            return [self._upstreams]
        return self._upstreams

    def append_upstream(self, upstreams: AnyTask | list[AnyTask]):
        upstream_list = [upstreams] if isinstance(upstreams, AnyTask) else upstreams
        for upstream in upstream_list:
            self.__append_upstream(upstream)

    def __append_upstream(self, upstream: AnyTask):
        # Make sure self._upstreams is a list
        if self._upstreams is None:
            self._upstreams = []
        elif isinstance(self._upstreams, AnyTask):
            self._upstreams = [self._upstreams]
        # Add upstream if it was not on self._upstreams
        if upstream not in self._upstreams:
            self._upstreams.append(upstream)

    def get_ctx(self, session: AnySession) -> AnyContext:
        ctx = session.get_ctx(self)
        # Enhance session ctx with current task env
        for env in self.envs:
            env.update_context(ctx)
        return ctx

    def run(
        self, session: AnySession | None = None, str_kwargs: dict[str, str] = {}
    ) -> Any:
        return asyncio.run(self._run_and_cleanup(session, str_kwargs))

    async def _run_and_cleanup(
        self,
        session: AnySession | None = None,
        str_kwargs: dict[str, str] = {},
    ) -> Any:
        current_task = asyncio.create_task(self.async_run(session, str_kwargs))
        try:
            result = await current_task
        finally:
            if session and not session.is_terminated:
                session.terminate()
            # Cancel all running tasks except the current one
            pending = [task for task in asyncio.all_tasks() if task is not current_task]
            for task in pending:
                task.cancel()
            if pending:
                try:
                    await asyncio.wait(pending, timeout=5)
                except asyncio.CancelledError:
                    pass
        return result

    async def async_run(
        self, session: AnySession | None = None, str_kwargs: dict[str, str] = {}
    ) -> Any:
        if session is None:
            session = Session(shared_ctx=SharedContext())
        # Update session
        self.__fill_shared_context_inputs(session.shared_ctx, str_kwargs)
        self.__fill_shared_context_envs(session.shared_ctx)
        result = await run_async(self.exec_root_tasks(session))
        return result

    def __fill_shared_context_inputs(
        self, shared_context: AnySharedContext, str_kwargs: dict[str, str] = {}
    ):
        for task_input in self.inputs:
            if task_input.name not in shared_context.input:
                str_value = str_kwargs.get(task_input.name, None)
                task_input.update_shared_context(shared_context, str_value)

    def __fill_shared_context_envs(self, shared_context: AnySharedContext):
        # Inject os environ
        os_env_map = {
            key: val for key, val in os.environ.items() if key not in shared_context.env
        }
        shared_context.env.update(os_env_map)

    async def exec_root_tasks(self, session: AnySession):
        session.set_main_task(self)
        session.state_logger.write(session.as_state_log())
        try:
            log_state = asyncio.create_task(self._log_session_state(session))
            root_tasks = [
                task
                for task in session.get_root_tasks(self)
                if session.is_allowed_to_run(task)
            ]
            root_task_coros = [
                run_async(root_task.exec_chain(session)) for root_task in root_tasks
            ]
            await asyncio.gather(*root_task_coros)
            await session.wait_deferred()
            session.terminate()
            await log_state
            return session.final_result
        except IndexError:
            return None
        except (asyncio.CancelledError, KeyboardInterrupt):
            ctx = self.get_ctx(session)
            ctx.log_info("Session terminated")
        finally:
            session.terminate()
            session.state_logger.write(session.as_state_log())
            ctx = self.get_ctx(session)
            ctx.log_debug(session)

    async def _log_session_state(self, session: AnySession):
        session.state_logger.write(session.as_state_log())
        while not session.is_terminated:
            await asyncio.sleep(0.1)
            session.state_logger.write(session.as_state_log())
        session.state_logger.write(session.as_state_log())

    async def exec_chain(self, session: AnySession):
        if session.is_terminated or not session.is_allowed_to_run(self):
            return
        result = await self.exec(session)
        # Get next tasks
        nexts = session.get_next_tasks(self)
        if session.is_terminated or len(nexts) == 0:
            return result
        # Run next tasks asynchronously
        next_coros = [run_async(next.exec_chain(session)) for next in nexts]
        return await asyncio.gather(*next_coros)

    async def exec(self, session: AnySession):
        ctx = self.get_ctx(session)
        if not session.is_allowed_to_run(self):
            # Task is not allowed to run, skip it for now.
            # This will be triggered later
            ctx.log_info("Not allowed to run")
            return
        if not self.__get_execute_condition(session):
            # Skip the task
            ctx.log_info("Marked as skipped")
            session.get_task_status(self).mark_as_skipped()
            return
        # Wait for task to be ready
        return await run_async(self.__exec_action_until_ready(session))

    def __get_execute_condition(self, session: Session) -> bool:
        ctx = self.get_ctx(session)
        return get_bool_attr(ctx, self._execute_condition, True, auto_render=True)

    async def __exec_action_until_ready(self, session: AnySession):
        ctx = self.get_ctx(session)
        readiness_checks = self.readiness_checks
        if len(readiness_checks) == 0:
            ctx.log_info("No readiness checks")
            # Task has no readiness check
            result = await run_async(self.__exec_action_and_retry(session))
            ctx.log_info("Marked as ready")
            session.get_task_status(self).mark_as_ready()
            return result
        # Start the task along with the readiness checks
        action_coro = asyncio.create_task(
            run_async(self.__exec_action_and_retry(session))
        )
        await asyncio.sleep(self._readiness_check_delay)
        readiness_check_coros = [
            run_async(check.exec_chain(session)) for check in readiness_checks
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
                run_async(self.__exec_monitoring(session, action_coro))
            )
            session.defer_monitoring(self, monitor_and_rerun_coro)
        return result

    async def __exec_monitoring(self, session: AnySession, action_coro: asyncio.Task):
        readiness_checks = self.readiness_checks
        failure_count = 0
        ctx = self.get_ctx(session)
        while not session.is_terminated:
            await asyncio.sleep(self._readiness_check_period)
            if failure_count < self._readiness_failure_threshold:
                for readiness_check in readiness_checks:
                    session.get_task_status(readiness_check).reset_history()
                    session.get_task_status(readiness_check).reset()
                    readiness_xcom: Xcom = ctx.xcom[self.name]
                    readiness_xcom.clear()
                readiness_check_coros = [
                    check.exec_chain(session) for check in readiness_checks
                ]
                try:
                    ctx.log_info("Checking")
                    await asyncio.wait_for(
                        asyncio.gather(*readiness_check_coros),
                        timeout=self._readiness_timeout,
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
            action_coro: Coroutine = asyncio.create_task(
                run_async(self.__exec_action_and_retry(session))
            )
            session.defer_action(self, action_coro)
            failure_count = 0
            ctx.log_info("Continue monitoring")

    async def __exec_action_and_retry(self, session: AnySession) -> Any:
        """
        Executes an action with retry logic.

        This method attempts to execute the action defined in `_exec_action` with a specified number of retries.
        If the action fails, it will retry after a specified period until the maximum number of attempts is reached.
        If the action succeeds, it marks the task as completed and executes any successors.
        If the action fails permanently, it marks the task as permanently failed and executes any fallbacks.

        Args:
            session (AnySession): The session object containing the task status and context.

        Returns:
            Any: The result of the executed action if successful.

        Raises:
            Exception: If the action fails permanently after all retry attempts.
        """
        ctx = self.get_ctx(session)
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
                task_xcom: Xcom = ctx.xcom.get(self.name)
                task_xcom.push(result)
                self.__skip_fallbacks(session)
                await run_async(self.__exec_successors(session))
                return result
            except (asyncio.CancelledError, KeyboardInterrupt):
                ctx.log_info("Marked as failed")
                session.get_task_status(self).mark_as_failed()
                return
            except BaseException as e:
                ctx.log_error(e)
                if attempt < max_attempt - 1:
                    ctx.log_info("Marked as failed")
                    session.get_task_status(self).mark_as_failed()
                    continue
                ctx.log_info("Marked as permanently failed")
                session.get_task_status(self).mark_as_permanently_failed()
                self.__skip_successors(session)
                await run_async(self.__exec_fallbacks(session))
                raise e

    async def __exec_successors(self, session: AnySession) -> Any:
        successors: list[AnyTask] = self.successors
        successor_coros = [
            run_async(successor.exec_chain(session)) for successor in successors
        ]
        await asyncio.gather(*successor_coros)

    def __skip_successors(self, session: AnySession) -> Any:
        for successor in self.successors:
            session.get_task_status(successor).mark_as_skipped()

    async def __exec_fallbacks(self, session: AnySession) -> Any:
        fallbacks: list[AnyTask] = self.fallbacks
        fallback_coros = [
            run_async(fallback.exec_chain(session)) for fallback in fallbacks
        ]
        await asyncio.gather(*fallback_coros)

    def __skip_fallbacks(self, session: AnySession) -> Any:
        for fallback in self.fallbacks:
            session.get_task_status(fallback).mark_as_skipped()

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
