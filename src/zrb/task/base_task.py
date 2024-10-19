from typing import Any, TextIO
from collections.abc import Callable
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..session.session import Session
from .any_task import AnyTask, State

import asyncio
import inspect
import os
import sys


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
        description: str | None = None,
        inputs: list[AnyInput] | None = None,
        envs: list[AnyEnv] | None = None,
        action: str | Callable[[AnyTask, Session], Any] | None = None,
        retries: int = 2,
        retry_period: float = 0,
        readiness_checks: list[AnyTask] | None = None,
        readiness_check_delay: float = 0,
        readiness_check_period: float = 0,
        upstreams: list[AnyTask] | None = None,
    ):
        self._name = name
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

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return self._description if self._description is not None else self.get_name()

    def get_envs(self) -> list[AnyEnv]:
        envs = []
        for upstream in self.get_upstreams():
            envs += upstream.get_envs()
        if self._envs is not None:
            envs += self._envs
        return envs

    def get_inputs(self) -> list[AnyInput]:
        inputs = []
        for upstream in self.get_upstreams():
            inputs += upstream.get_inputs()
        if self._inputs is not None:
            inputs += self._inputs
        return inputs

    def get_upstreams(self) -> list[AnyTask]:
        if self._upstreams is None:
            return []
        return self._upstreams

    def print(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        message = sep.join([f"{value}" for value in values])
        print(message, sep=sep, end=end, file=file, flush=flush)

    def run(self, session: Session | None = None) -> Any:
        return asyncio.run(self.async_run(session))

    async def async_run(self, session: Session | None = None) -> Any:
        if session is None:
            session = Session()
        # Update session
        self._update_session_inputs(session)
        self._update_session_envs(session)
        # Create state
        state = State(session=session)
        state.register_upstreams(self, self.get_upstreams())
        await self._async_run_root_tasks(state)
        await state.wait_long_run_coroutines()
        if self._name in session.xcoms:
            xcom = session.xcoms[self._name]
            if len(xcom) > 0:
                return xcom[len(xcom) - 1]
        return None

    def _update_session_envs(self, session: Session) -> Session:
        env_map = {key: val for key, val in os.environ.items()}
        for env in self.get_envs():
            env_map.update(env.get_env_map(session))
        env_map.update(session.envs)
        session.envs = env_map

    def _update_session_inputs(self, session: Session) -> Session:
        input_map = {}
        for task_input in self.get_inputs():
            input_map.update(
                {task_input.get_name(): task_input.get_value(session)}
            )
        input_map.update(session.inputs)
        session.inputs = input_map

    async def _async_run_root_tasks(self, state: State):
        root_tasks = [
            task for task in state.get_tasks()
            if state.is_allowed_to_run(task)
        ]
        coros = [
            root_task._async_run_and_trigger_downstreams(state)
            for root_task in root_tasks
        ]
        await asyncio.gather(*coros)

    async def _async_run_and_trigger_downstreams(self, state: State):
        if not state.is_allowed_to_run(self):
            return
        state.mark_task_as_started(self)
        result = await run_async(self._async_run_action_and_check_readiness, state)
        state.mark_task_as_completed(self)
        # Set xcoms
        session = state.get_session()
        if self._name not in session.xcoms:
            session.xcoms[self._name] = []
        session.xcoms[self._name].append(result)
        # Define callback
        downstreams = state.get_downstreams(self)
        if len(downstreams) == 0:
            return
        coros = [
            downstream._async_run_and_trigger_downstreams(state)
            for downstream in downstreams
        ]
        await asyncio.gather(*coros)

    async def _async_run_action_and_check_readiness(self, state: State) -> Any:
        session = state.get_session()
        if self._readiness_checks is None or len(self._readiness_checks) == 0:
            return await self._async_run_action(session)
        action = asyncio.create_task(self._async_run_action(session))
        coros = [
            check._async_run_action_and_check_readiness(state)
            for check in self._readiness_checks
        ]
        result = await asyncio.gather(*coros)
        state.register_long_run_coroutine(action)
        return result

    async def _async_run_action_with_retry(self, session: Session) -> Any:
        for attempt in range(self._retries + 1):
            if attempt > 0:
                await asyncio.sleep(self._retry_period)
            try:
                return await self._async_run_action(session)
            except KeyboardInterrupt as e:
                raise e
            except Exception:
                continue
        raise Exception(f"failed after {self._retries + 1} attempts")

    async def _async_run_action(self, session: Session) -> Any:
        if self._action is None:
            return
        if isinstance(self._action, str):
            return session.render(self._action)
        return await run_async(self._action, self, session)
