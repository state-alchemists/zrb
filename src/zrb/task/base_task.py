from typing import Any
from collections.abc import Callable
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..session.shared_context import AnySharedContext
from ..session.shared_context import SharedContext
from ..session.context import Context
from ..session.any_session import AnySession
from ..session.session import Session
from .any_task import AnyTask

import asyncio
import inspect
import os


async def run_async(fn: Callable, *args: Any, **kwargs: Any) -> Any:
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    coro = asyncio.to_thread(fn, *args, **kwargs)
    task = asyncio.create_task(coro)
    return await task


class BaseTask(AnyTask):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        inputs: list[AnyInput] | AnyInput | None = None,
        envs: list[AnyEnv] | AnyEnv | None = None,
        action: str | Callable[[Context], Any] | None = None,
        retries: int = 2,
        retry_period: float = 0,
        readiness_checks: list[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0,
        readiness_check_period: float = 0,
        upstreams: list[AnyTask] | AnyTask | None = None,
    ):
        self._name = name
        self._color = color
        self._icon = icon
        self._description = description
        self._inputs = inputs
        self._envs = envs
        self._retries = retries
        self._retry_period = retry_period
        self._upstreams = upstreams
        self._readiness_checks = readiness_checks
        self._readiness_check_delay = readiness_check_delay
        self._readiness_check_period = readiness_check_period
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

    def get_icon(self) -> int | None:
        return self._icon

    def get_description(self) -> str:
        return self._description if self._description is not None else self.get_name()

    def get_envs(self) -> list[AnyEnv]:
        envs = []
        for upstream in self.get_upstreams():
            envs += upstream.get_envs()
        if isinstance(self._inputs, AnyEnv):
            envs.append(self._envs)
        if self._envs is not None:
            envs += self._envs
        return envs

    def get_inputs(self) -> list[AnyInput]:
        inputs = []
        for upstream in self.get_upstreams():
            inputs += upstream.get_inputs()
        if isinstance(self._inputs, AnyInput):
            inputs.append(self._inputs)
        if self._inputs is not None:
            inputs += self._inputs
        return inputs

    def get_upstreams(self) -> list[AnyTask]:
        if self._upstreams is None:
            return []
        if isinstance(self._upstreams, AnyTask):
            return [self._upstreams]
        return self._upstreams

    def set_upstreams(self, upstreams: AnyTask | list[AnyTask]):
        if isinstance(upstreams, AnyTask):
            self._upstreams.append(upstreams)
        self._upstreams += upstreams

    def get_readiness_checks(self) -> list[AnyTask]:
        if self._readiness_checks is None:
            return []
        if isinstance(self._readiness_checks, AnyTask):
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
        session.register_task(self)
        await self._async_run_root_tasks(session)
        await session.wait_long_run_coroutines()
        return session.peek_task_xcom(self)

    def _fill_shared_context_envs(self, shared_context: AnySharedContext):
        # Inject os environ
        os_env_map = {
            key: val for key, val in os.environ.items()
            if key not in shared_context.envs
        }
        shared_context.envs.update(os_env_map)
        # Inject environment from task's envs
        for env in self.get_envs():
            env.update_shared_context(shared_context)

    def _fill_shared_context_inputs(self, shared_context: AnySharedContext):
        for task_input in self.get_inputs():
            if task_input.get_name() not in shared_context.inputs:
                task_input.update_shared_context(shared_context)

    async def _async_run_root_tasks(self, session: AnySession):
        root_tasks = [
            task for task in session.get_tasks()
            if session.is_allowed_to_run(task)
        ]
        coros = [
            root_task._async_run_with_downstreams(session)
            for root_task in root_tasks
        ]
        await asyncio.gather(*coros)

    async def _async_run_with_downstreams(self, session: AnySession):
        if not session.is_allowed_to_run(self):
            return
        session.mark_task_as_started(self)
        await run_async(self._async_run_action_and_check_readiness, session)
        session.mark_task_as_completed(self)
        # Get current task's downstreams
        downstreams = session.get_downstreams(self)
        if len(downstreams) == 0:
            return
        # Run all the downstreams asynchronously
        coros = [
            downstream._async_run_with_downstreams(session)
            for downstream in downstreams
        ]
        await asyncio.gather(*coros)

    async def _async_run_action_and_check_readiness(self, session: AnySession):
        context = session.get_context(self)
        if self._readiness_checks is None or len(self._readiness_checks) == 0:
            result = await self._async_run_action_and_retry(context)
            session.append_task_xcom(self, result)
            return result
        coro = asyncio.create_task(self._async_run_action_and_retry(context))
        readiness_checks = [
            check._async_run_with_downstreams(session)
            for check in self._readiness_checks
        ]
        result = await asyncio.gather(*readiness_checks)
        session.register_long_run_coroutine(self, coro)
        return result

    async def _async_run_action_and_retry(self, context: Context) -> Any:
        max_attempt = self._retries + 1
        context.set_max_attempt(max_attempt)
        for attempt in range(max_attempt):
            context.set_attempt(attempt + 1)
            if attempt > 0:
                await asyncio.sleep(self._retry_period)
            try:
                return await self._async_run_action(context)
            except KeyboardInterrupt as e:
                raise e
            except Exception:
                continue
        raise Exception(f"failed after {self._retries + 1} attempts")

    async def _async_run_action(self, context: Context) -> Any:
        if self._action is None:
            return
        if isinstance(self._action, str):
            return context.render(self._action)
        return await run_async(self._action, context)
