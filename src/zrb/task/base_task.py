from typing import Any
from collections.abc import Callable
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..context.shared_context import AnySharedContext
from ..context.shared_context import SharedContext
from ..context.context import Context
from ..session.any_session import AnySession
from ..session.session import Session
from ..util.run import run_async
from ..util.cli.style import stylize_error
from ..util.string.conversion import to_boolean
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
        action: str | Callable[[Context], Any] | None = None,
        execute_condition: bool | str | Callable[[Context], bool] = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0,
        readiness_check_period: float = 0,
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
        self._readiness_check_delay = readiness_check_delay
        self._readiness_check_period = readiness_check_period
        self._execute_condition = execute_condition
        self._action = action

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self._name}>"

    def __rshift__(self, other: AnyTask | list[AnyTask]):
        if isinstance(other, AnyTask):
            other.set_upstreams(self)
        if isinstance(other, list):
            for task in other:
                task.set_upstreams(self)

    def __lshift__(self, other: AnyTask | list[AnyTask]):
        self.set_upstreams(other)

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
        if isinstance(upstreams, AnyTask):
            self._upstreams.append(upstreams)
        self._upstreams += upstreams

    def get_readiness_checks(self) -> list[AnyTask]:
        if self._readiness_checks is None:
            return []
        elif isinstance(self._readiness_checks, AnyTask):
            return [self._readiness_checks]
        return self._readiness_checks

    def run(self, shared_context: AnySharedContext | None = None) -> Any:
        return asyncio.run(self.async_run(shared_context))

    async def async_run(self, shared_context: AnySharedContext | None = None) -> Any:
        if shared_context is None:
            shared_context = SharedContext()
        # Update session
        self._fill_shared_context_inputs(shared_context)
        self._fill_shared_context_envs(shared_context)
        # Create state
        session = Session(shared_context=shared_context)
        return await run_async(self.exec_root_tasks, session)

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
            task for task in session.get_tasks()
            if session.is_allowed_to_run(task)
        ]
        root_task_coros = [
            run_async(root_task.exec_chain, session)
            for root_task in root_tasks
        ]
        await asyncio.gather(*root_task_coros)
        await session.wait_deffered_task_coroutines()
        return session.peek_task_xcom(self)

    async def exec_chain(self, session: AnySession):
        if not session.is_allowed_to_run(self):
            # Task is not allowed to run, skip it for now.
            # This will be triggered later
            return
        execute_condition = await self._check_execute_condition(session)
        if not execute_condition:
            # Skip the task
            session.mark_task_as_skipped(self)
        else:
            # Wait for task to be ready
            await run_async(self._exec_action_until_ready, session)
        # Get next tasks
        nexts = session.get_next_tasks(self)
        if len(nexts) == 0:
            return
        # Run next tasks asynchronously
        coros = [
            run_async(next.exec_chain, session)
            for next in nexts
        ]
        await asyncio.gather(*coros)

    async def _check_execute_condition(self, session: Session) -> bool:
        if callable(self._execute_condition):
            context = session.get_context()
            return await run_async(self._execute_condition, context)
        if isinstance(self._execute_condition, str):
            context = session.get_context()
            return to_boolean(context.render(self._execute_condition))
        return self._execute_condition

    async def _exec_action_until_ready(self, session: AnySession):
        readiness_checks = self.get_readiness_checks()
        if len(readiness_checks) == 0:
            # Task has no readiness check
            session.mark_task_as_started(self)
            result = await run_async(self._exec_action_and_retry, session)
            session.mark_task_as_completed(self)
            session.append_task_xcom(self, result)
            return result
        # Start the task along with the readiness checks
        session.mark_task_as_started(self)
        coro = asyncio.create_task(run_async(self._exec_action_and_retry, session))
        readiness_check_coros = [
            run_async(check.exec_chain, session) for check in readiness_checks
        ]
        # Only wait for readiness checks and mark the task as ready
        result = await asyncio.gather(*readiness_check_coros)
        session.mark_task_as_ready(self)
        # Defer task's coroutines, will be waited later
        session.defer_task_coroutine(self, coro)
        return result

    async def _exec_action_and_retry(self, session: AnySession) -> Any:
        ctx = session.get_context(self)
        max_attempt = self._retries + 1
        ctx.set_max_attempt(max_attempt)
        for attempt in range(max_attempt):
            ctx.set_attempt(attempt + 1)
            if attempt > 0:
                # apply retry period only if this is not the first attempt
                await asyncio.sleep(self._retry_period)
            try:
                return await run_async(self._exec_action, ctx)
            except KeyboardInterrupt:
                return
            except Exception as e:
                ctx.print(stylize_error(f"{e}"))
                if attempt < max_attempt - 1:
                    continue
                session.mark_task_as_permanently_failed(self)
                await run_async(self._exec_fallbacks, session)
                raise e

    async def _exec_fallbacks(self, session: AnySession) -> Any:
        fallbacks: list[AnyTask] = self.get_fallbacks()
        fallback_coros = [
            run_async(fallback.exec_chain, session)
            for fallback in fallbacks
        ]
        await asyncio.gather(*fallback_coros)

    async def _exec_action(self, ctx: Context) -> Any:
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
        return await run_async(self._action, ctx)
