from typing import Any, Callable, Iterable, Optional, Union
from typeguard import typechecked
from .base_task import BaseTask, Group
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_input.base_input import BaseInput
from ..config.config import default_shell

import asyncio
import atexit
import os
import pathlib
import signal


class CmdResult():
    def __init__(self, output: str, error: str):
        self.output = output
        self.error = error


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
    runner.register(run_server)
    ```
    '''

    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        inputs: Iterable[BaseInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        executable: Optional[str] = None,
        cmd: Union[str, Iterable[str]] = '',
        cmd_path: str = '',
        cwd: Optional[Union[str, pathlib.Path]] = None,
        upstreams: Iterable[BaseTask] = [],
        checkers: Iterable[BaseTask] = [],
        checking_interval: float = 0,
        retry: int = 2,
        retry_interval: float = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        skip_execution: Union[bool, str, Callable[..., bool]] = False
    ):
        BaseTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            upstreams=upstreams,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            skip_execution=skip_execution
        )
        max_output_line = self.ensure_non_negative(
            max_output_line, 'Find negative max_output_line'
        )
        max_error_line = self.ensure_non_negative(
            max_error_line, 'Find negative max_error_line'
        )
        self._cmd = cmd
        self._cmd_path = cmd_path
        self._set_cwd(cwd)
        self._max_output_size = max_output_line
        self._max_error_size = max_error_line
        self._output_buffer: Iterable[str] = []
        self._error_buffer: Iterable[str] = []
        if executable is None and default_shell != '':
            executable = default_shell
        self._executable = executable
        self._process: Optional[asyncio.subprocess.Process]
        self._preexec_fn = preexec_fn

    def _set_cwd(
        self, cwd: Optional[Union[str, pathlib.Path]]
    ):
        if cwd is None:
            self.cwd: Union[str, pathlib.Path] = os.getcwd()
            return
        self.cwd: Union[str, pathlib.Path] = cwd

    def create_main_loop(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., CmdResult]:
        return super().create_main_loop(env_prefix, raise_error)

    def _print_result(self, result: CmdResult):
        if result.output == '':
            return
        print(result.output)

    async def run(self, *args: Any, **kwargs: Any) -> CmdResult:
        cmd = self._get_cmd_str()
        env = self.get_env_map()
        self.print_out_dark('Run script: ' + self._get_multiline_repr(cmd))
        self.print_out_dark('Current working directory: ' + self.cwd)
        self._output_buffer = []
        self._error_buffer = []
        process = await asyncio.create_subprocess_shell(
            cmd,
            cwd=self.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            shell=True,
            executable=self._executable,
            close_fds=True,
            preexec_fn=self._preexec_fn,
            bufsize=0
        )
        self.set_task_pid(process.pid)
        self._process = process
        atexit.register(self._at_exit)
        await self._wait_process(process)
        atexit.unregister(self._at_exit)
        # get output and error
        output = '\n'.join(self._output_buffer)
        error = '\n'.join(self._error_buffer)
        # get return code
        return_code = process.returncode
        if return_code != 0:
            self.log_info(f'Exit status: {return_code}')
            raise Exception(
                f'Process {self._name} exited ({return_code}): {error}'
            )
        return CmdResult(output, error)

    def _at_exit(self):
        self.retry = 0
        if self._process.returncode is None:
            try:
                self.log_info(f'Send SIGTERM to process {self._process.pid}')
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            except Exception:
                self.log_error(
                    f'Cannot send SIGTERM to process {self._process.pid}'
                )

    async def _wait_process(self, process: asyncio.subprocess.Process):
        # Create queue
        stdout_queue = asyncio.Queue()
        stderr_queue = asyncio.Queue()
        # Read from streams and put into queue
        stdout_process = asyncio.create_task(self._queue_stream(
            process.stdout, stdout_queue
        ))
        stderr_process = asyncio.create_task(self._queue_stream(
            process.stderr, stderr_queue
        ))
        # Handle messages in queue
        stdout_log_process = asyncio.create_task(self._log_from_queue(
            stdout_queue, self.print_out,
            self._output_buffer, self._max_output_size
        ))
        stderr_log_process = asyncio.create_task(self._log_from_queue(
            stderr_queue, self.print_err,
            self._error_buffer, self._max_error_size
        ))
        # wait process
        await process.wait()
        # wait reader and logger
        await stdout_process
        await stderr_process
        await stdout_queue.put(None)
        await stderr_queue.put(None)
        await stdout_log_process
        await stderr_log_process

    def _get_cmd_str(self) -> str:
        return self._create_cmd_str(self._cmd_path, self._cmd)

    def _create_cmd_str(
        self, cmd_path: str, cmd: Union[str, Iterable[str]]
    ) -> str:
        if cmd_path != '':
            return self.render_file(cmd_path)
        if isinstance(cmd, str):
            return self.render_str(cmd)
        return self.render_str('\n'.join(list(cmd)))

    async def _queue_stream(self, stream, queue: asyncio.Queue):
        while True:
            try:
                line = await stream.readline()
            except Exception as e:
                line = str(e)
            if not line:
                break
            await queue.put(line)

    async def _log_from_queue(
        self,
        queue: asyncio.Queue,
        print_log: Callable[[str], None],
        buffer: Iterable[str],
        max_size: int
    ):
        while True:
            line = await queue.get()
            if not line:
                break
            line_str = line.decode().rstrip()
            self._add_to_buffer(buffer, max_size, line_str)
            print_log(line_str)

    def _add_to_buffer(
        self, buffer: Iterable[str], max_size: int, new_line: str
    ):
        if len(buffer) >= max_size:
            buffer.pop(0)
        buffer.append(new_line)
