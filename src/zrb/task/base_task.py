from typing import Any, List, Optional, TypeVar
from pydantic import BaseModel, Field
from ..task_input.base_input import BaseInput
from ..helper.random_maker import get_random_icon, get_random_name

import asyncio
import datetime
import logging
import os
import sys

Task = TypeVar('Task', bound='BaseTask')


class BaseTask(BaseModel):
    name: Optional[str]
    icon: Optional[str] = None
    inputs: List[BaseInput] = []
    upstreams: List[Task] = []
    readiness_probes: List[Task] = []
    checking_interval: int = 1
    retry: int = 2
    retry_interval: int = 1
    _is_done: Field(default=False)
    _attempt: Field(default=1)
    _task_pid: Field(default=os.getpid)

    def get_icon(self) -> str:
        '''
        Getting task icon
        '''
        if self.icon is None or self.icon == '':
            self.icon = get_random_icon()
        return self.icon

    def get_name(self) -> str:
        '''
        Getting task name
        '''
        if self.name is None or self.name == '':
            self.name = get_random_name()
        return self.name

    def get_upstreams(self) -> List[Task]:
        '''
        Getting upstreams of this task
        '''
        return self.upstreams

    def get_inputs(self) -> List[BaseInput]:
        ''''
        Getting inputs of this task
        '''
        inputs: List[BaseInput] = []
        for upstream in self.get_upstreams():
            upstream_inputs = upstream.get_inputs()
            inputs = upstream_inputs + inputs
        inputs = inputs + self.inputs
        return inputs

    def print_out(self, msg: Any):
        prefix = self._get_log_prefix()
        print(f'{prefix} {msg}')

    def print_err(self, msg: Any):
        prefix = self._get_log_prefix()
        print(f'{prefix} {msg}', file=sys.stderr)

    async def run(self, *args, **kwargs: Any):
        '''
        Override task running logic
        '''
        logging.info(
            f'Running {self.name} with args {args} and kwargs {kwargs}'
        )

    async def check(self) -> bool:
        '''
        Override task checking logic
        '''
        if len(self.readiness_probes) == 0:
            # There is no readiness probes defined
            # Just wait for self._is_done signal
            return self._is_done
        # There are readiness probes
        check_runners: List[asyncio.Task] = []
        for readiness_task in self.readiness_probes:
            check_runners.append(readiness_task.run())
        await asyncio.gather(*check_runners)

    async def _check(self) -> bool:
        while not await self.check():
            logging.info(f'Task {self.name} is not ready')
            asyncio.sleep(self.checking_interval)
        logging.info(f'Task {self.name} is ready')
        return True

    async def _run(self, *args, **kwargs: Any):
        tasks: List[asyncio.Task] = []
        for upstream in self.get_upstreams():
            tasks.append(upstream._run(*args, **kwargs))
        tasks.append(self._run_current_task(*args, **kwargs))
        await asyncio.gather(*tasks)

    async def _run_current_task(self, *args, **kwargs: Any):
        await self._check_upstream()
        await self._run_with_retry(*args, **kwargs)

    async def _check_upstream(self):
        check_runners: List[asyncio.Task] = []
        for upstream in self.get_upstreams():
            check_runners.append(upstream._check())
        await asyncio.gather(*check_runners)

    async def _run_with_retry(self, *args, **kwargs):
        max_attempt = self.retry + 1
        retrying = True
        while self._attempt <= max_attempt:
            try:
                await self.run(*args, **kwargs)
                retrying = False
            except Exception:
                logging.error(' '.join([
                    f'Error while running {self.name}, ',
                    f'attempt {self._attempt} of {max_attempt}'
                ]), exc_info=True)
                if self._attempt == max_attempt:
                    raise
                self._attempt += 1
                await asyncio.sleep(self.retry_interval)
            if not retrying:
                break
        # By default, self.check() will return the value of __is_done property
        # Here we indicate that the task has been successfully performed
        self._is_done = True

    def _get_log_prefix(self) -> str:
        attempt = self._attempt
        max_attempt = self.retry + 1
        now = datetime.datetime.now().isoformat()
        pid = self._task_pid
        info_prefix = f'{now} PID={pid}, attempt {attempt} of {max_attempt}'
        icon = self.get_icon()
        name = self.get_name()
        return f'{info_prefix} {icon} {name}'
