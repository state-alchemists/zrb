from typing import Any, List, Mapping, Optional, TypeVar
from .base_model import TaskModel
from ..task_input.base_input import BaseInput
from ..task_env.env import Env

import asyncio

Task = TypeVar('Task', bound='BaseTask')


class BaseTask(TaskModel):
    name: str
    icon: Optional[str] = None
    color: Optional[str] = None
    inputs: List[BaseInput] = []
    envs: List[Env] = []
    upstreams: List[Task] = []
    checkers: List[Task] = []
    checking_interval: int = 1
    retry: int = 2
    retry_interval: int = 1

    async def run(self, *args: Any, **kwargs: Any):
        '''
        Override task running logic
        '''
        self.log_debug(
            f'Run with args {args} and kwargs {kwargs}'
        )

    async def check(self) -> bool:
        '''
        Override task checking logic
        '''
        return self.is_done()

    def get_all_inputs(self) -> List[BaseInput]:
        ''''
        Getting inputs of this task
        '''
        inputs: List[BaseInput] = []
        for upstream in self.upstreams:
            upstream_inputs = upstream.get_all_inputs()
            inputs = inputs + upstream_inputs
        inputs = inputs + self.inputs
        return inputs

    def create_main_loop(self, env_prefix: str):
        def main_loop(*args, **kwargs):
            '''
            Task main loop.
            '''
            async def run_and_check_all_async():
                self._set_keyval(input_map=kwargs, env_prefix=env_prefix)
                await asyncio.gather(
                    self._run_with_upstreams(*args, **kwargs),
                    self._loop_check(celebrate=True)
                )
            return asyncio.run(run_and_check_all_async())
        return main_loop

    async def _loop_check(self, celebrate: bool = False) -> bool:
        while not await self._check():
            self.log_debug('Task is not ready')
            await asyncio.sleep(self.checking_interval)
        self.end_timer()
        self.log_info('Task is ready')
        if celebrate:
            self.show_celebration()
        return True

    async def _check(self) -> bool:
        '''
        Check current task readiness.
        - If self.checkers is defined, 
          this will return True once every self.checkers is completed
        - Otherwise, this will return check method's return value.
        '''
        if len(self.checkers) == 0:
            return await self.check()
        check_processes: List[asyncio.Task] = []
        for checker_task in self.checkers:
            check_processes.append(checker_task.run())
        await asyncio.gather(*check_processes)
        return True

    async def _run_with_upstreams(self, *args: Any, **kwargs: Any):
        processes: List[asyncio.Task] = []
        # Add upstream tasks to processes
        for upstream_task in self.upstreams:
            processes.append(
                upstream_task._run_with_upstreams(*args, **kwargs)
            )
        # Add current task to processes
        processes.append(self._run(*args, **kwargs))
        # Wait everything to complete
        await asyncio.gather(*processes)

    async def _run(self, *args, **kwargs: Any):
        self.start_timer()
        # get upstream checker
        upstream_check_processes: List[asyncio.Task] = []
        for upstream_task in self.upstreams:
            upstream_check_processes.append(upstream_task._loop_check())
        # wait all upstream checkers to complete
        await asyncio.gather(*upstream_check_processes)
        # start running task
        while self.should_attempt():
            try:
                await self.run(*args, **kwargs)
                break
            except Exception:
                self.log_error('Encounter error')
                if self.is_last_attempt():
                    raise
                self.increase_attempt()
                await asyncio.sleep(self.retry_interval)
        self.mark_as_done()

    def _set_keyval(self, input_map: Mapping[str, Any], env_prefix: str):
        self.set_local_keyval(input_map=input_map, env_prefix=env_prefix)
        for upstream_task in self.upstreams:
            upstream_task._set_keyval(
                input_map=input_map, env_prefix=env_prefix
            )
        local_env_map = self.get_env_map()
        for checker_task in self.checkers:
            checker_task._set_keyval(
                input_map=input_map, env_prefix=env_prefix
            )
            # Checker task should be able to read local env
            checker_task.inject_env_map(local_env_map)
