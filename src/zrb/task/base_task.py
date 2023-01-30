from typing import Any, List, Mapping, Optional, TypeVar
from .base_model import TaskModel
from ..task_input.base_input import BaseInput
from ..task_env.env import Env
from ..task_group.group import Group
from ..helper.list.append_unique import append_unique

import asyncio

TTask = TypeVar('TTask', bound='BaseTask')


class BaseTask(TaskModel):
    name: str
    group: Optional[Group]
    icon: Optional[str] = None
    description: str = ''
    color: Optional[str] = None
    inputs: List[BaseInput] = []
    envs: List[Env] = []
    upstreams: List[TTask] = []
    checkers: List[TTask] = []
    checking_interval: float = 0.3
    retry: int = 2
    retry_interval: float = 1

    # flag whehther checking has been success or not
    zrb_is_checked: bool = False
    # flag whehther execution has been done or not
    zrb_is_executed: bool = False

    async def run(self, **kwargs: Any):
        '''
        Override task running logic
        '''
        self.log_debug(
            f'Run with kwargs: {kwargs}'
        )

    async def check(self) -> bool:
        '''
        Override task checking logic
        '''
        return self.is_done()

    def get_all_inputs(self) -> List[BaseInput]:
        ''''
        Getting all inputs of this task and all its upstream, non-duplicated.
        '''
        inputs: List[BaseInput] = []
        for upstream in self.upstreams:
            upstream_inputs = upstream.get_all_inputs()
            append_unique(inputs, *upstream_inputs)
        append_unique(inputs, *self.inputs)
        return inputs

    def get_description(self) -> str:
        if self.description != '':
            return self.description
        return self.name

    def create_main_loop(self, env_prefix: str):
        def main_loop(**kwargs: Any):
            '''
            Task main loop.
            '''
            async def run_and_check_all_async():
                self._set_keyval(input_map=kwargs, env_prefix=env_prefix)
                processes = [
                    asyncio.create_task(
                        self._run_with_upstreams(**kwargs)
                    ),
                    asyncio.create_task(self._loop_check(celebrate=True))
                ]
                await asyncio.gather(*processes)
            try:
                return asyncio.run(run_and_check_all_async())
            except Exception:
                self.log_error('Encounter error')
            finally:
                self.play_bell()
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

    async def _check_with_flag(self) -> bool:
        if self.zrb_is_checked:
            self.log_debug('Skip checking, because checking flag has been set')
            return True
        check_result = await self._check()
        if check_result:
            self.zrb_is_checked = True
            self.log_debug('Set checking flag')
        return check_result

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
            check_processes.append(asyncio.create_task(checker_task.run()))
        await asyncio.gather(*check_processes)
        return True

    async def _run_with_upstreams(self, **kwargs: Any):
        processes: List[asyncio.Task] = []
        # Add upstream tasks to processes
        for upstream_task in self.upstreams:
            processes.append(asyncio.create_task(
                upstream_task._run_with_upstreams(**kwargs)
            ))
        # Add current task to processes
        processes.append(self._run(**kwargs))
        # Wait everything to complete
        await asyncio.gather(*processes)

    async def _run(self, **kwargs: Any):
        if self.zrb_is_executed:
            self.log_debug('Skip running, because execution flag has been set')
            return
        self.zrb_is_executed = True
        self.log_debug('Set execution flag and running')
        self.start_timer()
        # get upstream checker
        upstream_check_processes: List[asyncio.Task] = []
        for upstream_task in self.upstreams:
            upstream_check_processes.append(asyncio.create_task(
                upstream_task._loop_check()
            ))
        # wait all upstream checkers to complete
        await asyncio.gather(*upstream_check_processes)
        # start running task
        while self.should_attempt():
            try:
                await self.run(**kwargs)
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
