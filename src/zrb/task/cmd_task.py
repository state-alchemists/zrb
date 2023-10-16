from zrb.helper.typing import (
    Any, Callable, Iterable, List, Mapping, Optional, Union, TypeVar
)
from zrb.helper.typecheck import typechecked
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput
from zrb.config.config import default_shell

import asyncio
import atexit
import os
import pathlib
import signal
import sys
import subprocess
import time

_has_stty = True
try:
    _original_stty = subprocess.getoutput('stty -g').rstrip()
except Exception:
    _has_stty = False


def _reset_stty():
    global _has_stty
    if _has_stty:
        try:
            subprocess.run(['stty', _original_stty], check=True)
        except Exception:
            _has_stty = False


CmdVal = Union[str, Iterable[str], Callable[..., Union[Iterable[str], str]]]
TCmdTask = TypeVar('TCmdTask', bound='CmdTask')


class CmdResult():
    def __init__(self, output: str, error: str):
        self.output = output
        self.error = error


class CmdGlobalState():
    def __init__(self):
        self.no_more_attempt: bool = False
        self.is_killed_by_signal: bool = False


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

    _pids: List[int] = []
    _global_state = CmdGlobalState()

    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        executable: Optional[str] = None,
        cmd: CmdVal = '',
        cmd_path: CmdVal = '',
        cwd: Optional[Union[str, pathlib.Path]] = None,
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        skip_execution: Union[bool, str, Callable[..., bool]] = False,
        return_upstream_result: bool = False
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
            skip_execution=skip_execution,
            return_upstream_result=return_upstream_result
        )
        max_output_line = max_output_line if max_output_line > 0 else 1
        max_error_line = max_error_line if max_error_line > 0 else 1
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

    def copy(self) -> TCmdTask:
        return super().copy()

    def _set_cwd(
        self, cwd: Optional[Union[str, pathlib.Path]]
    ):
        if cwd is None:
            self.cwd: Union[str, pathlib.Path] = os.getcwd()
            return
        self.cwd: Union[str, pathlib.Path] = cwd

    def to_function(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., CmdResult]:
        return super().to_function(env_prefix, raise_error)

    def print_result(self, result: CmdResult):
        if result.output == '':
            return
        print(result.output)

    def _get_shell_env_map(self) -> Mapping[str, Any]:
        env_map = self.get_env_map()
        input_map = self.get_input_map()
        for input_name, input_value in input_map.items():
            upper_input_name = '_INPUT_' + input_name.upper()
            if upper_input_name not in env_map:
                env_map[upper_input_name] = f'{input_value}'
        return env_map

    async def run(self, *args: Any, **kwargs: Any) -> CmdResult:
        cmd = self._get_cmd_str(*args, **kwargs)
        env_map = self._get_shell_env_map()
        self.print_out_dark('Run script: ' + self._get_multiline_repr(cmd))
        self.print_out_dark('Working directory: ' + self.cwd)
        self._output_buffer = []
        self._error_buffer = []
        process = await asyncio.create_subprocess_shell(
            cmd,
            cwd=self.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env_map,
            shell=True,
            executable=self._executable,
            close_fds=True,
            preexec_fn=self._preexec_fn,
            bufsize=0
        )
        self._set_task_pid(process.pid)
        self._pids.append(process.pid)
        self._process = process
        signal.signal(signal.SIGINT, self._on_kill)
        signal.signal(signal.SIGTERM, self._on_kill)
        atexit.register(self._on_exit)
        await self._wait_process(process)
        self.log_info('Process completed')
        atexit.unregister(self._on_exit)
        output = '\n'.join(self._output_buffer)
        error = '\n'.join(self._error_buffer)
        # get return code
        return_code = process.returncode
        self.log_info(f'Exit status: {return_code}')
        if return_code != 0 and not self._global_state.is_killed_by_signal:
            raise Exception(
                f'Process {self._name} exited ({return_code}): {error}'
            )
        return CmdResult(output, error)

    def _should_attempt(self) -> bool:
        if self._global_state.no_more_attempt:
            return False
        return super()._should_attempt()

    def _is_last_attempt(self) -> bool:
        if self._global_state.no_more_attempt:
            return True
        return super()._is_last_attempt()

    def _on_kill(self, signum: Any, frame: Any):
        self._global_state.no_more_attempt = True
        self._global_state.is_killed_by_signal = True
        self.print_out_dark(f'Getting signal {signum}')
        for pid in self._pids:
            self._kill_by_pid(pid)
        self.print_out_dark(f'Exiting with signal {signum}')
        sys.exit(signum)

    def _on_exit(self):
        self._global_state.no_more_attempt = True
        self._kill_by_pid(self._process.pid)

    def _kill_by_pid(self, pid: int):
        '''
        Kill a pid, gracefully
        '''
        try:
            process_ever_exists = False
            if self._is_process_exist(pid):
                process_ever_exists = True
                self.print_out_dark(f'Send SIGTERM to process {pid}')
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                time.sleep(0.5)
            if self._is_process_exist(pid):
                self.print_out_dark(f'Send SIGINT to process {pid}')
                os.killpg(os.getpgid(pid), signal.SIGINT)
                time.sleep(0.5)
            if self._is_process_exist(pid):
                self.print_out_dark(f'Send SIGKILL to process {pid}')
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            if process_ever_exists:
                self.print_out_dark(f'Process {pid} is killed successfully')
        except Exception:
            self.log_error(f'Cannot kill process {pid}')

    def _is_process_exist(self, pid: int) -> bool:
        try:
            os.killpg(os.getpgid(pid), 0)
            return True
        except ProcessLookupError:
            return False

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

    def _get_cmd_str(self, *args: Any, **kwargs: Any) -> str:
        return self._create_cmd_str(self._cmd_path, self._cmd, *args, **kwargs)

    def _create_cmd_str(
        self, cmd_path: CmdVal, cmd: CmdVal, *args: Any, **kwargs: Any
    ) -> str:
        if not isinstance(cmd_path, str) or cmd_path != '':
            if callable(cmd_path):
                return self._render_cmd_path_str(cmd_path(*args, **kwargs))
            return self._render_cmd_path_str(cmd_path)
        if callable(cmd):
            return self._render_cmd_str(cmd(*args, **kwargs))
        return self._render_cmd_str(cmd)

    def _render_cmd_path_str(self, cmd_path: Union[str, Iterable[str]]) -> str:
        if isinstance(cmd_path, str):
            return self.render_file(cmd_path)
        return '\n'.join([
            self.render_file(cmd_path_str)
            for cmd_path_str in cmd_path
        ])

    def _render_cmd_str(self, cmd: Union[str, Iterable[str]]) -> str:
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
            line_str = line.decode('utf-8').rstrip()
            self._add_to_buffer(buffer, max_size, line_str)
            _reset_stty()
            print_log(line_str)
            _reset_stty()

    def _add_to_buffer(
        self, buffer: Iterable[str], max_size: int, new_line: str
    ):
        if len(buffer) >= max_size:
            buffer.pop(0)
        buffer.append(new_line)
    
    def __repr__(self) -> str:
        return f'<CmdTask name={self._name}>'
