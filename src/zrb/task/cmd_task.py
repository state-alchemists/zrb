import os
from functools import partial

from zrb.attr.type import BoolAttr, IntAttr, StrAttr
from zrb.cmd.cmd_result import CmdResult
from zrb.cmd.cmd_val import AnyCmdVal, CmdVal, SingleCmdVal
from zrb.config import DEFAULT_SHELL, WARN_UNRECOMMENDED_COMMAND
from zrb.context.any_context import AnyContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.util.attr import get_int_attr, get_str_attr
from zrb.util.cmd.command import check_unrecommended_commands, run_command
from zrb.util.cmd.remote import get_remote_cmd_script
from zrb.xcom.xcom import Xcom


class CmdTask(BaseTask):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: list[AnyInput | None] | AnyInput | None = None,
        env: list[AnyEnv | None] | AnyEnv | None = None,
        shell: StrAttr | None = None,
        render_shell: bool = True,
        shell_flag: StrAttr | None = None,
        render_shell_flag: bool = True,
        remote_host: StrAttr | None = None,
        render_remote_host: bool = True,
        remote_port: IntAttr | None = None,
        render_remote_port: bool = True,
        remote_user: StrAttr | None = None,
        render_remote_user: bool = True,
        remote_password: StrAttr | None = None,
        render_remote_password: bool = True,
        remote_ssh_key: StrAttr | None = None,
        render_remote_ssh_key: bool = True,
        cmd: CmdVal = "",
        render_cmd: bool = True,
        cwd: str | None = None,
        render_cwd: bool = True,
        plain_print: bool = False,
        warn_unrecommended_command: bool | None = None,
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
        successor: list[AnyTask] | AnyTask | None = None,
    ):
        super().__init__(
            name=name,
            color=color,
            icon=icon,
            description=description,
            cli_only=cli_only,
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
            successor=successor,
        )
        self._shell = shell
        self._render_shell = render_shell
        self._shell_flag = shell_flag
        self._render_shell_flag = render_shell_flag
        self._remote_host = remote_host
        self._render_remote_host = render_remote_host
        self._remote_port = remote_port
        self._render_remote_port = render_remote_port
        self._remote_user = remote_user
        self._render_remote_user = render_remote_user
        self._remote_password = remote_password
        self._render_remote_password = render_remote_password
        self._remote_ssh_key = remote_ssh_key
        self._render_remote_ssh_key = render_remote_ssh_key
        self._cmd = cmd
        self._render_cmd = render_cmd
        self._cwd = cwd
        self._render_cwd = render_cwd
        self._max_output_line = max_output_line
        self._max_error_line = max_error_line
        self._should_plain_print = plain_print
        self._should_warn_unrecommended_command = warn_unrecommended_command

    async def _exec_action(self, ctx: AnyContext) -> CmdResult:
        """Turn _cmd attribute into subprocess.Popen and execute it as task's action.

        Args:
            session (AnySession): The shared session.

        Returns:
            Any: The result of the action execution.
        """
        cmd_script = self._get_cmd_script(ctx)
        ctx.log_debug(f"Script: {self.__get_multiline_repr(cmd_script)}")
        shell = self._get_shell(ctx)
        ctx.log_debug(f"Shell: {shell}")
        shell_flag = self._get_shell_flag(ctx)
        cwd = self._get_cwd(ctx)
        ctx.log_debug(f"Working directory: {cwd}")
        env_map = self.__get_env_map(ctx)
        ctx.log_debug(f"Environment map: {env_map}")
        if self._get_should_warn_unrecommended_commands():
            self._check_unrecommended_commands(ctx, shell, cmd_script)
        ctx.log_info("Running script")
        print_method = (
            partial(ctx.print, plain=True) if self._should_plain_print else ctx.print
        )
        xcom_pid_key = f"{self.name}-pid"
        ctx.xcom[xcom_pid_key] = Xcom([])
        cmd_result, return_code = await run_command(
            cmd=[shell, shell_flag, cmd_script],
            cwd=cwd,
            env_map=env_map,
            print_method=print_method,
            register_pid_method=lambda pid: ctx.xcom.get(xcom_pid_key).push(pid),
            max_output_line=self._max_output_line,
            max_error_line=self._max_error_line,
        )
        # Check for errors
        if return_code > 0:
            raise Exception(f"Process {self._name} exited ({return_code})")
        ctx.log_info(f"Exit status: {return_code}")
        return cmd_result

    def _get_should_warn_unrecommended_commands(self):
        if self._should_warn_unrecommended_command is None:
            return WARN_UNRECOMMENDED_COMMAND
        return self._should_warn_unrecommended_command

    def _check_unrecommended_commands(
        self, ctx: AnyContext, shell: str, cmd_script: str
    ):
        if shell.endswith("bash") or shell.endswith("zsh"):
            unrecommended_commands = check_unrecommended_commands(cmd_script)
            if unrecommended_commands:
                ctx.log_warning("The script contains unrecommended commands")
            for command, reason in unrecommended_commands.items():
                ctx.log_warning(f"- {command}: {reason}")

    def __get_env_map(self, ctx: AnyContext) -> dict[str, str]:
        envs = {key: val for key, val in ctx.env.items()}
        envs["_ZRB_SSH_PASSWORD"] = self._get_remote_password(ctx)
        envs["PYTHONBUFFERED"] = "1"
        return envs

    def _get_shell(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._shell, DEFAULT_SHELL, auto_render=self._render_shell
        )

    def _get_shell_flag(self, ctx: AnyContext) -> str:
        default_shell_flags = {
            "node": "-e",
            "ruby": "-e",
            "php": "-r",
            "powershell": "/c",
        }
        default_shell_flag = default_shell_flags.get(self._get_shell(ctx).lower(), "-c")
        return get_str_attr(
            ctx,
            self._shell_flag,
            default_shell_flag,
            auto_render=self._render_shell_flag,
        )

    def _get_remote_host(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._remote_host, "", auto_render=self._render_remote_host
        )

    def _get_remote_port(self, ctx: AnyContext) -> int:
        return get_int_attr(
            ctx, self._remote_port, 22, auto_render=self._render_remote_port
        )

    def _get_remote_user(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._remote_user, "", auto_render=self._render_remote_user
        )

    def _get_remote_password(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._remote_password,
            "",
            auto_render=self._render_remote_password,
        )

    def _get_remote_ssh_key(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx, self._remote_ssh_key, "", auto_render=self._render_remote_ssh_key
        )

    def _get_cwd(self, ctx: AnyContext) -> str:
        cwd = get_str_attr(ctx, self._cwd, os.getcwd(), auto_render=self._render_cwd)
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
            cmd_val_list = [
                self.__render_single_cmd_val(ctx, single_cmd_val)
                for single_cmd_val in cmd_val
            ]
            return "\n".join(
                [cmd_val for cmd_val in cmd_val_list if cmd_val is not None]
            )
        return self.__render_single_cmd_val(ctx, cmd_val)

    def __render_single_cmd_val(
        self, ctx: AnyContext, single_cmd_val: SingleCmdVal
    ) -> str | None:
        if callable(single_cmd_val):
            return single_cmd_val(ctx)
        if isinstance(single_cmd_val, str):
            if self._render_cmd:
                return ctx.render(single_cmd_val)
            return single_cmd_val
        if isinstance(single_cmd_val, AnyCmdVal):
            return single_cmd_val.to_str(ctx)
        return None

    def __get_multiline_repr(self, text: str) -> str:
        lines_repr: list[str] = []
        lines = text.split("\n")
        if len(lines) == 1:
            return lines[0]
        for index, line in enumerate(lines):
            line_number_repr = str(index + 1).rjust(4, "0")
            lines_repr.append(f"   {line_number_repr} | {line}")
        return "\n" + "\n".join(lines_repr)
