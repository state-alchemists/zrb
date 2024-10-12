import asyncio
import atexit
import logging
import os
import pathlib
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from typing import Any, Optional, TypeVar, Union

from zrb.config.config import DEFAULT_SHELL, LOGGING_LEVEL
from zrb.helper.accessories.color import colored
from zrb.helper.asyncio_task import stop_asyncio_sync
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import JinjaTemplate
from zrb.task.any_task import AnyTask
from zrb.task.any_task_event_handler import (
    OnFailed,
    OnReady,
    OnRetry,
    OnSkipped,
    OnStarted,
    OnTriggered,
    OnWaiting,
)
from zrb.task.base_task.base_task import BaseTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.cmd_task", attrs=["dark"]))

_has_stty = True
try:
    _original_stty = subprocess.getoutput("stty -g").rstrip()
except Exception:
    _has_stty = False


def _reset_stty():
    global _has_stty
    if _has_stty:
        try:
            subprocess.run(["stty", _original_stty], check=True)
        except Exception:
            _has_stty = False


def _log_error(message: Any):
    if LOGGING_LEVEL > logging.ERROR:
        return
    colored_message = colored(f"{message}", color="red", attrs=["bold"])
    logger.error(colored_message, exc_info=True)


def _print_out_dark(message: Any):
    message_str = f"{message}"
    print(colored(message_str, attrs=["dark"]), file=sys.stderr)


CmdVal = Union[
    JinjaTemplate,
    Iterable[JinjaTemplate],
    Callable[..., Union[Iterable[JinjaTemplate], JinjaTemplate]],
]
TCmdTask = TypeVar("TCmdTask", bound="CmdTask")


class CmdResult:
    def __init__(self, output: str, error: str):
        self.output = output
        self.error = error

    def __str__(self) -> str:
        return self.output


class CmdGlobalState:
    def __init__(self):
        self.no_more_attempt: bool = False
        self.is_killed_by_signal: bool = False


@typechecked
class CmdTask(BaseTask):
    """
    Command Task.
    You can use this task to run shell command.

    Examples:
        >>> from zrb import runner, CmdTask, StrInput, Env
        >>> hello = CmdTask(
        >>>     name='hello',
        >>>     inputs=[StrInput(name='name', default='World')],
        >>>     envs=[Env(name='HOME_DIR', os_name='HOME')],
        >>>     cmd=[
        >>>         'echo Hello {{ input.name }}',
        >>>         'echo Home directory is: $HOME_DIR',
        >>>     ]
        >>> )
        >>> runner.register(hello)
    """

    _pids: list[int] = []
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
        description: str = "",
        executable: Optional[str] = None,
        cmd: CmdVal = "",
        cmd_path: CmdVal = "",
        cwd: Optional[Union[JinjaTemplate, pathlib.Path]] = None,
        should_render_cwd: bool = True,
        upstreams: Iterable[AnyTask] = [],
        fallbacks: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0.05,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
        should_print_cmd_result: bool = True,
        should_show_cmd: bool = True,
        should_show_working_directory: bool = True,
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
            fallbacks=fallbacks,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
        )
        max_output_line = max_output_line if max_output_line > 0 else 1
        max_error_line = max_error_line if max_error_line > 0 else 1
        self._cmd = cmd
        self._cmd_path = cmd_path
        self.__set_cwd(cwd)
        self._should_render_cwd = should_render_cwd
        self._max_output_size = max_output_line
        self._max_error_size = max_error_line
        self._output_buffer: Iterable[str] = []
        self._error_buffer: Iterable[str] = []
        if executable is None and DEFAULT_SHELL != "":
            executable = DEFAULT_SHELL
        self._executable = executable
        self._should_print_cmd_result = should_print_cmd_result
        self._should_show_working_directory = should_show_working_directory
        self._should_show_cmd = should_show_cmd

    def copy(self) -> TCmdTask:
        return super().copy()

    def set_cwd(self, cwd: Union[str, pathlib.Path]):
        self.__set_cwd(cwd)

    def __set_cwd(self, cwd: Optional[Union[str, pathlib.Path]]):
        if cwd is None:
            self._cwd: Union[str, pathlib.Path] = os.getcwd()
            return
        self._cwd: Union[str, pathlib.Path] = os.path.abspath(cwd)

    def to_function(
        self,
        env_prefix: str = "",
        raise_error: bool = True,
        is_async: bool = False,
        show_done_info: bool = True,
        should_clear_xcom: bool = False,
        should_stop_looper: bool = False,
    ) -> Callable[..., CmdResult]:
        return super().to_function(
            env_prefix=env_prefix,
            raise_error=raise_error,
            is_async=is_async,
            show_done_info=show_done_info,
            should_clear_xcom=should_clear_xcom,
            should_stop_looper=should_stop_looper,
        )

    def print_result(self, result: CmdResult):
        if not self._should_print_cmd_result or result.output == "":
            return
        print(result.output)

    async def run(self, *args: Any, **kwargs: Any) -> CmdResult:
        cmd = self.get_cmd_script(*args, **kwargs)
        if self._should_show_cmd:
            self.print_out_dark("Run script: " + self.__get_multiline_repr(cmd))
        cwd = self._get_cwd()
        if self._should_show_working_directory:
            self.print_out_dark("Working directory: " + cwd)
        self._output_buffer = []
        self._error_buffer = []
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.get_env_map(),
            shell=True,
            text=True,
            executable=self._executable,
            bufsize=1,
        )
        self._set_task_pid(process.pid)
        self._pids.append(process.pid)
        self._process = process
        try:
            signal.signal(signal.SIGINT, self.__on_kill)
            signal.signal(signal.SIGTERM, self.__on_kill)
        except Exception as e:
            self.print_err(e)
        atexit.register(self.__on_exit)
        await self.__wait_process(process)
        self.log_info("Process completed")
        atexit.unregister(self.__on_exit)
        output = "\n".join(self._output_buffer)
        error = "\n".join(self._error_buffer)
        # get return code
        return_code = process.returncode
        self.log_info(f"Exit status: {return_code}")
        if return_code != 0 and not self._global_state.is_killed_by_signal:
            raise Exception(f"Process {self._name} exited ({return_code}): {error}")
        self.set_task_xcom(key="output", value=output)
        self.set_task_xcom(key="error", value=error)
        return CmdResult(output, error)

    def _get_cwd(self) -> Union[str, pathlib.Path]:
        if self._should_render_cwd and isinstance(self._cwd, str):
            return self.render_str(self._cwd)
        return self._cwd

    def get_cmd_script(self, *args: Any, **kwargs: Any) -> str:
        return self._create_cmd_script(self._cmd_path, self._cmd, *args, **kwargs)

    def _create_cmd_script(
        self, cmd_path: CmdVal, cmd: CmdVal, *args: Any, **kwargs: Any
    ) -> str:
        if not isinstance(cmd_path, str) or cmd_path != "":
            if callable(cmd_path):
                return self.__get_rendered_cmd_path(cmd_path(*args, **kwargs))
            return self.__get_rendered_cmd_path(cmd_path)
        if callable(cmd):
            return self.__get_rendered_cmd(cmd(*args, **kwargs))
        return self.__get_rendered_cmd(cmd)

    def __get_rendered_cmd_path(self, cmd_path: Union[str, Iterable[str]]) -> str:
        if isinstance(cmd_path, str):
            return self.render_file(cmd_path)
        return "\n".join([self.render_file(cmd_path_str) for cmd_path_str in cmd_path])

    def __get_rendered_cmd(
        self, cmd: Union[JinjaTemplate, Iterable[JinjaTemplate]]
    ) -> str:
        if isinstance(cmd, str):
            return self.render_str(cmd)
        return self.render_str("\n".join(list(cmd)))

    def __get_multiline_repr(self, text: str) -> str:
        lines_repr: Iterable[str] = []
        lines = text.split("\n")
        if len(lines) == 1:
            return lines[0]
        for index, line in enumerate(lines):
            line_number_repr = str(index + 1).rjust(4, "0")
            lines_repr.append(f"        {line_number_repr} | {line}")
        return "\n" + "\n".join(lines_repr)
