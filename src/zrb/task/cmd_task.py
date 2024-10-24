from collections.abc import Callable, Mapping
from .any_task import AnyTask
from .base_task import BaseTask
from .cmd_data import Cmd, CmdPath, CmdResult, CmdVal, SingleCmdVal
from ..config import DEFAULT_SHELL
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..session.context import Context
from ..util.cmd.remote import get_remote_cmd_script

import io
import os
import threading
import subprocess
import sys


class CmdTask(BaseTask):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        input: list[AnyInput] | AnyInput | None = None,
        env: list[AnyEnv] | AnyEnv | None = None,
        shell: str | None = None,
        remote_host: str | None = None,
        remote_port: str | int | None = None,
        remote_user: str | None = None,
        remote_password: str | None = None,
        remote_ssh_key: str | None = None,
        cmd: CmdVal = "",
        cwd: str | None = None,
        auto_render_cmd: bool = True,
        auto_render_cwd: bool = True,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        execute_condition: bool | str | Callable[[Context], bool] = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0,
        readiness_check_period: float = 0,
        upstream: list[AnyTask] | AnyTask | None = None,
        fallback: list[AnyTask] | AnyTask | None = None,
    ):
        super().__init__(
            name=name,
            color=color,
            icon=icon,
            description=description,
            input=input,
            env=env,
            execute_condition=execute_condition,
            retries=retries,
            retry_period=retry_period,
            readiness_check=readiness_check,
            readiness_check_delay=readiness_check_delay,
            readiness_check_period=readiness_check_period,
            upstream=upstream,
            fallback=fallback,
        )
        self._shell = shell
        self._remote_host = remote_host
        self._remote_port = remote_port
        self._remote_user = remote_user
        self._remote_password = remote_password
        self._remote_ssh_key = remote_ssh_key
        self._cmd = cmd
        self._cwd = cwd
        self._auto_render_cmd = auto_render_cmd
        self._auto_render_cwd = auto_render_cwd
        self._max_output_line = max_output_line
        self._max_error_line = max_error_line

    async def _exec_action(self, ctx: Context) -> CmdResult:
        """Turn _cmd attribute into subprocess.Popen and execute it as task's action.

        Args:
            session (AnySession): The shared session.

        Returns:
            Any: The result of the action execution.
        """
        cmd_script = self.__get_local_or_remote_cmd_script(ctx)
        ctx.log_debug(f"Run script: {self.__get_multiline_repr(cmd_script)}")
        cwd = self._get_cwd(ctx)
        ctx.log_debug(f"Working directory: {cwd}")
        cmd_process = subprocess.Popen(
            cmd_script,
            cwd=cwd,
            stdin=sys.stdin if sys.stdin.isatty() else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.__get_envs(ctx),
            shell=True,
            text=True,
            executable=self._shell if self._shell is not None else DEFAULT_SHELL,
            bufsize=0,
        )
        stdout, stderr = [], []
        stdout_thread = threading.Thread(
            target=self.__make_reader(
                ctx, cmd_process.stdout, max_line=self._max_output_line, lines=stdout
            )
        )
        stderr_thread = threading.Thread(
            target=self.__make_reader(
                ctx, cmd_process.stderr, max_line=self._max_output_line, lines=stderr
            )
        )
        stdout_thread.start()
        stderr_thread.start()
        try:
            process_error = None
            try:
                cmd_process.wait()
            except Exception as e:
                process_error = e
            stdout_thread.join()
            stderr_thread.join()
            output = "\n".join(stdout)
            error = "\n".join(stderr)
            # get return code
            return_code = cmd_process.returncode
            if process_error is not None:
                raise Exception(process_error)
            if return_code != 0:
                ctx.log_error(f"Exit status: {return_code}")
                raise Exception(f"Process {self._name} exited ({return_code}): {error}")
            return CmdResult(output, error)
        finally:
            self.__terminate_process(ctx, cmd_process)

    def __get_envs(self, ctx: Context) -> Mapping[str, str]:
        envs = {key: val for key, val in ctx.env.items()}
        if self._remote_password is not None:
            envs["_ZRB_SSH_PASSWORD"] = ctx.render(self._remote_password)

    def __make_reader(
        self, ctx: Context, stream: io.TextIOWrapper, max_line: int, lines: list[str],
    ) -> Callable:
        def read_lines():
            for line in stream:
                line = line.rstrip()
                ctx.print(line)
                lines.append(line)
                if len(lines) > max_line:
                    lines.pop(0)
        return read_lines

    def __terminate_process(self, ctx: Context, cmd_process: subprocess.Popen[str]):
        """Terminate the shell script if it's still running."""
        if cmd_process.poll() is None:  # If the process is still running
            cmd_process.terminate()  # Gracefully terminate the process
            try:
                ctx.log_info("Waiting for process termination")
                cmd_process.wait(timeout=5)  # Give it time to terminate
            except subprocess.TimeoutExpired:
                ctx.log_info("Killing the process")
                cmd_process.kill()  # Forcefully kill if not terminated

    def _get_cwd(self, ctx: Context):
        cwd = self._cwd
        if cwd is None:
            cwd = os.getcwd()
        if self._auto_render_cwd:
            cwd = ctx.render(cwd)
        return os.path.abspath(cwd)

    def __get_local_or_remote_cmd_script(self, ctx: Context) -> str:
        local_cmd_script = self._get_cmd_script(ctx)
        if self._remote_host is None:
            return local_cmd_script
        return get_remote_cmd_script(
            cmd_script=local_cmd_script,
            host=ctx.render(self._remote_host),
            port=ctx.render(self._remote_port),
            user=ctx.render(self._remote_user),
            password="$_ZRB_SSH_PASSWORD",
            use_password=ctx.render(self._remote_password) != "",
            ssh_key=ctx.render(self._remote_ssh_key),
        )

    def _get_cmd_script(self, ctx: Context) -> str:
        return self._render_cmd_val(ctx, self._cmd)

    def _render_cmd_val(self, ctx: Context, cmd_val: CmdVal) -> str:
        if isinstance(cmd_val, list):
            return "\n".join([
                self.__render_single_cmd_val(ctx, single_cmd_val)
                for single_cmd_val in cmd_val
            ])
        return self._render_cmd_val(ctx, cmd_val)

    def __render_single_cmd_val(
        self, ctx: Context, single_cmd_val: SingleCmdVal
    ) -> str:
        if callable(single_cmd_val):
            return single_cmd_val(ctx)
        if isinstance(single_cmd_val, CmdPath):
            return single_cmd_val.read(ctx)
        if isinstance(single_cmd_val, Cmd):
            return single_cmd_val.render(ctx)
        if self._auto_render_cmd:
            return ctx.render(single_cmd_val)
        return single_cmd_val

    def __get_multiline_repr(self, text: str) -> str:
        lines_repr: list[str] = []
        lines = text.split("\n")
        if len(lines) == 1:
            return lines[0]
        for index, line in enumerate(lines):
            line_number_repr = str(index + 1).rjust(4, "0")
            lines_repr.append(f"   {line_number_repr} | {line}")
        return "\n" + "\n".join(lines_repr)
