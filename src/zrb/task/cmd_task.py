from typing import Any, Callable, Iterable, List, Optional, Union
from typeguard import typechecked
from .base_task import BaseTask
from ..task_env.env import Env
from ..task_input.base_input import BaseInput
from ..task_group.group import Group

import asyncio


@typechecked
class CmdTask(BaseTask):
    '''
    Command Task.
    You can use this task to run shell command.

    For example:
    ```python
    # run a simple task
    hello = CmdTask(
        name='hello',
        inputs=[StrInput(name='name', default='World')],
        envs=[Env(name='HOME_DIR', os_name='HOME')],
        cmd=[
            'echo Hello {{ input.name }}',
            'echo Home directory is: $HOME_DIR',
        ]
    )
    runner.register(hello)

    # run a long running process
    run_server = CmdTask(
        name='run',
        inputs=[StrInput(name='dir', default='.')],
        envs=[Env(name='PORT', os_name='WEB_PORT', default='3000')],
        cmd='python -m http.server $PORT --directory {{input.dir}}',
        checkers=[HTTPChecker(port='{{env.PORT}}')]
    )
    ```
    '''

    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        inputs: List[BaseInput] = [],
        envs: List[Env] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        cmd: Union[str, Iterable[str]] = '',
        cmd_path: str = '',
        upstreams: List[BaseTask] = [],
        checkers: List[BaseTask] = [],
        checking_interval: float = 0.1,
        retry: int = 2,
        retry_interval: float = 1,
    ):
        BaseTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            icon=icon,
            color=color,
            description=description,
            upstreams=upstreams,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval
        )
        self.cmd = cmd
        self.cmd_path = cmd_path

    async def run(self, **kwargs: Any):
        cmd = self.get_cmd()
        env = self.get_env_map()
        self.log_debug(f'Run command: {cmd}\nwith env: {env}')
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            shell=True
        )
        self.set_task_pid(process.pid)
        # Create queue
        stdout_queue = asyncio.Queue()
        stderr_queue = asyncio.Queue()
        # Create reader task
        stdout_task = asyncio.create_task(self._stream_reader(
            process.stdout, stdout_queue
        ))
        stderr_task = asyncio.create_task(self._stream_reader(
            process.stderr, stderr_queue
        ))
        # Create logger task
        stdout_logger_task = asyncio.create_task(
            self._stream_logger(self.print_out, stdout_queue)
        )
        stderr_logger_task = asyncio.create_task(
            self._stream_logger(self.print_err, stderr_queue)
        )
        # wait process
        await process.wait()
        # wait reader and logger
        await stdout_task
        await stderr_task
        await stdout_queue.put(None)
        await stderr_queue.put(None)
        await stdout_logger_task
        await stderr_logger_task
        # get return code
        return_code = process.returncode
        if return_code != 0:
            self.log_debug(f'Exit status: {return_code}')
            raise Exception(f'Process {self.name} exited ({return_code})')

    def get_cmd(self) -> str:
        if self.cmd_path != '':
            cmd_path = self.render_str(self.cmd_path)
            with open(cmd_path, 'r') as file:
                return self.render_str(file.read())
        if isinstance(self.cmd, str):
            return self.render_str(self.cmd)
        return self.render_str('\n'.join(self.cmd))

    async def _stream_reader(self, stream, queue: asyncio.Queue):
        while True:
            line = await stream.readline()
            if not line:
                break
            await queue.put(line)

    async def _stream_logger(
        self, print_log: Callable[[str], None], queue: asyncio.Queue
    ):
        while True:
            line = await queue.get()
            if not line:
                break
            print_log(line.decode().rstrip())
