from collections.abc import Callable, Mapping
from .any_task import AnyTask
from .base_task import BaseTask
from ..attr.type import StrAttr, IntAttr
from ..cmd.cmd_result import CmdResult
from ..cmd.cmd_val import AnyCmdVal, CmdVal, SingleCmdVal
from ..config import DEFAULT_SHELL
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..context.context import Context
from ..util.cmd.remote import get_remote_cmd_script
from ..util.attr import get_str_attr, get_int_attr

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
        shell: StrAttr | None = None,
        auto_render_shell: bool = True,
        remote_host: StrAttr | None = None,
        auto_render_remote_host: bool = True,
        remote_port: IntAttr | None = None,
        auto_render_remote_port: bool = True,
        remote_user: StrAttr | None = None,
        auto_render_remote_user: bool = True,
        remote_password: StrAttr | None = None,
        auto_render_remote_password: bool = True,
        remote_ssh_key: StrAttr | None = None,
        auto_render_remote_ssh_key: bool = True,
        cmd: CmdVal = "",
        auto_render_cmd: bool = True,
        cwd: str | None = None,
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
        self._auto_render_shell = auto_render_shell
        self._remote_host = remote_host
        self._auto_render_remote_host = auto_render_remote_host
        self._remote_port = remote_port
        self._auto_render_remote_port = auto_render_remote_port
        self._remote_user = remote_user
        self._auto_render_remote_user = auto_render_remote_user
        self._remote_password = remote_password
        self._auto_render_remote_password = auto_render_remote_password
        self._remote_ssh_key = remote_ssh_key
        self._auto_render_remote_ssh_key = auto_render_remote_ssh_key
        self._cmd = cmd
        self._auto_render_cmd = auto_render_cmd
        self._cwd = cwd
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
        cmd_script = self._get_cmd_script(ctx)
        cwd = self._get_cwd(ctx)
        shell = self._get_shell(ctx)
        ctx.log_info("Running script")
        ctx.log_debug(f"Shell: {shell}")
        ctx.log_debug(f"Script: {self.__get_multiline_repr(cmd_script)}")
        ctx.log_debug(f"Working directory: {cwd}")
        cmd_process = subprocess.Popen(
            cmd_script,
            cwd=cwd,
            stdin=sys.stdin if sys.stdin.isatty() else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.__get_env_map(ctx),
            shell=True,
            text=True,
            executable=shell,
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

    def __get_env_map(self, ctx: Context) -> Mapping[str, str]:
        envs = {key: val for key, val in ctx._env.items()}
        envs["_ZRB_SSH_PASSWORD"] = self._get_remote_password(ctx)

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

    def _get_shell(self, ctx: Context):
        return get_str_attr(
            ctx, self._shell, DEFAULT_SHELL, auto_render=self._auto_render_shell
        )

    def _get_remote_host(self, ctx: Context):
        return get_str_attr(
            ctx, self._remote_host, "", auto_render=self._auto_render_remote_host
        )

    def _get_remote_port(self, ctx: Context):
        return get_int_attr(
            ctx, self._remote_port, 22, auto_render=self._auto_render_remote_port
        )

    def _get_remote_user(self, ctx: Context):
        return get_str_attr(
            ctx, self._remote_user, "", auto_render=self._auto_render_remote_user
        )

    def _get_remote_password(self, ctx: Context) -> str:
        return get_str_attr(
            ctx, self._remote_password, "", auto_render=self._auto_render_remote_password
        )

    def _get_remote_ssh_key(self, ctx: Context):
        return get_str_attr(
            ctx, self._remote_ssh_key, "", auto_render=self._auto_render_remote_ssh_key
        )

    def _get_cwd(self, ctx: Context) -> str:
        cwd = get_str_attr(
            ctx, self._cwd, os.getcwd(), auto_render=self._auto_render_cwd
        )
        if cwd is None:
            cwd = os.getcwd()
        return os.path.abspath(cwd)

    def _get_cmd_script(self, ctx: Context) -> str:
        if self._remote_host is None:
            return self._get_local_cmd_script(ctx)
        return self._get_remote_cmd_script(ctx)

    def _get_remote_cmd_script(self, ctx: Context) -> str:
        return get_remote_cmd_script(
            cmd_script=self._get_local_cmd_script(ctx),
            host=self._get_remote_host(ctx),
            port=self._get_remote_port(ctx),
            user=self._get_remote_user(ctx),
            password="$_ZRB_SSH_PASSWORD",
            use_password=self._get_remote_password(ctx) != "",
            ssh_key=self._get_remote_ssh_key(ctx),
        )

    def _get_local_cmd_script(self, ctx: Context) -> str:
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
        if isinstance(single_cmd_val, str):
            if self._auto_render_cmd:
                return ctx.render(single_cmd_val)
            return single_cmd_val
        if isinstance(single_cmd_val, AnyCmdVal):
            return single_cmd_val.to_str(ctx)

    def __get_multiline_repr(self, text: str) -> str:
        lines_repr: list[str] = []
        lines = text.split("\n")
        if len(lines) == 1:
            return lines[0]
        for index, line in enumerate(lines):
            line_number_repr = str(index + 1).rjust(4, "0")
            lines_repr.append(f"   {line_number_repr} | {line}")
        return "\n" + "\n".join(lines_repr)
