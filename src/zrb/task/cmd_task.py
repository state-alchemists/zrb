from collections.abc import Mapping
from .any_task import AnyTask
from .base_task import BaseTask
from ..attr.type import BoolAttr, StrAttr, IntAttr
from ..cmd.cmd_result import CmdResult
from ..cmd.cmd_val import AnyCmdVal, CmdVal, SingleCmdVal
from ..config import DEFAULT_SHELL
from ..env.any_env import AnyEnv
from ..input.any_input import AnyInput
from ..context.any_context import AnyContext
from ..util.cmd.remote import get_remote_cmd_script
from ..util.attr import get_str_attr, get_int_attr

import asyncio
import os
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
        execute_condition: BoolAttr = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
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
            readiness_failure_threshold=readiness_failure_threshold,
            readiness_timeout=readiness_timeout,
            monitor_readiness=monitor_readiness,
            upstream=upstream,
            fallback=fallback,
        )
        self._shell = shell
        self._auto_render_shell = auto_render_shell
        self._remote_host = remote_host
        self._auto_render_remote_host = auto_render_remote_host
        self._remote_port = remote_port
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

    async def _exec_action(self, ctx: AnyContext) -> CmdResult:
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
        cmd_process = await asyncio.create_subprocess_exec(
            shell,
            "-c",
            cmd_script,
            cwd=cwd,
            stdin=sys.stdin if sys.stdin.isatty() else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.__get_env_map(ctx),
            bufsize=0,
        )
        stdout_task = asyncio.create_task(
            self._read_stream(cmd_process.stdout, ctx.print, self._max_output_line)
        )
        stderr_task = asyncio.create_task(
            self._read_stream(cmd_process.stderr, ctx.print, self._max_error_line)
        )
        # Wait for process to complete and gather stdout/stderr
        return_code = await cmd_process.wait()
        stdout = await stdout_task
        stderr = await stderr_task
        # Check for errors
        if return_code != 0:
            ctx.log_error(f"Exit status: {return_code}")
            raise Exception(f"Process {self._name} exited ({return_code}): {stderr}")
        return CmdResult(stdout, stderr)

    def __get_env_map(self, ctx: AnyContext) -> Mapping[str, str]:
        envs = {key: val for key, val in ctx.env.items()}
        envs["_ZRB_SSH_PASSWORD"] = self._get_remote_password(ctx)

    async def _read_stream(self, stream, log_method, max_lines):
        lines = []
        while True:
            line = await stream.readline()
            if not line:
                break
            line = line.decode("utf-8").strip()
            lines.append(line.strip())  # Already a string due to text=True
            if len(lines) > max_lines:
                lines.pop(0)  # Keep only the last max_lines
            log_method(line.strip())
        return "\n".join(lines)

    def _get_shell(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._shell, DEFAULT_SHELL, auto_render=self._auto_render_shell
        )

    def _get_remote_host(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._remote_host, "", auto_render=self._auto_render_remote_host
        )

    def _get_remote_port(self, ctx: AnyContext) -> int:
        return get_int_attr(ctx, self._remote_port, 22, auto_render=True)

    def _get_remote_user(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._remote_user, "", auto_render=self._auto_render_remote_user
        )

    def _get_remote_password(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._remote_password, "", auto_render=self._auto_render_remote_password
        )

    def _get_remote_ssh_key(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._remote_ssh_key, "", auto_render=self._auto_render_remote_ssh_key
        )

    def _get_cwd(self, ctx: AnyContext) -> str:
        cwd = get_str_attr(
            ctx, self._cwd, os.getcwd(), auto_render=self._auto_render_cwd
        )
        if cwd is None:
            cwd = os.getcwd()
        return os.path.abspath(cwd)

    def _get_cmd_script(self, ctx: AnyContext) -> str:
        if self._remote_host is None:
            return self._get_local_cmd_script(ctx)
        return self._get_remote_cmd_script(ctx)

    def _get_remote_cmd_script(self, ctx: AnyContext) -> str:
        return get_remote_cmd_script(
            cmd_script=self._get_local_cmd_script(ctx),
            host=self._get_remote_host(ctx),
            port=self._get_remote_port(ctx),
            user=self._get_remote_user(ctx),
            password="$_ZRB_SSH_PASSWORD",
            use_password=self._get_remote_password(ctx) != "",
            ssh_key=self._get_remote_ssh_key(ctx),
        )

    def _get_local_cmd_script(self, ctx: AnyContext) -> str:
        return self._render_cmd_val(ctx, self._cmd)

    def _render_cmd_val(self, ctx: AnyContext, cmd_val: CmdVal) -> str:
        if isinstance(cmd_val, list):
            return "\n".join([
                self.__render_single_cmd_val(ctx, single_cmd_val)
                for single_cmd_val in cmd_val
            ])
        return self.__render_single_cmd_val(ctx, cmd_val)

    def __render_single_cmd_val(
        self, ctx: AnyContext, single_cmd_val: SingleCmdVal
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
