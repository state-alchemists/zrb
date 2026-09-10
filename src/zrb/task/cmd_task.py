import os
from collections.abc import Sequence
from functools import partial

from zrb.attr.type import BoolAttr, IntAttr, StrAttr
from zrb.cmd.any_cmd_val import AnyCmdVal
from zrb.cmd.cmd_result import CmdResult
from zrb.cmd.cmd_val import CmdVal, SingleCmdVal
from zrb.config.config import CFG
from zrb.config.helper import get_shell_name
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.base.base_task import BaseTask
from zrb.util.attr import get_int_attr, get_str_attr
from zrb.util.cmd.command import check_unrecommended_commands, run_command
from zrb.util.cmd.remote import get_remote_cmd_script
from zrb.util.secret import redact_env_map
from zrb.xcom.xcom import Xcom


class CmdTaskError(RuntimeError):
    """A shell command exited non-zero.

    Carries `return_code` so `zrb <task>` can exit with the code the command
    exited with instead of a flat 1 — a CmdTask wrapping a linter or a test
    runner has an exit code that means something to whatever called zrb.
    """

    def __init__(self, task_name: str, return_code: int) -> None:
        super().__init__(f"Process {task_name} exited ({return_code})")
        self.return_code = return_code


class CmdTask(BaseTask):
    def __init__(
        self,
        name: str,
        *,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: Sequence[AnyInput | None] | AnyInput | None = None,
        env: Sequence[AnyEnv | None] | AnyEnv | None = None,
        shell: StrAttr | None = None,
        shell_flag: StrAttr | None = None,
        remote_host: StrAttr | None = None,
        remote_port: IntAttr | None = None,
        remote_user: StrAttr | None = None,
        remote_password: StrAttr | None = None,
        remote_ssh_key: StrAttr | None = None,
        cmd: CmdVal = "",
        cwd: str | None = None,
        plain_print: bool = False,
        warn_unrecommended_command: bool | None = None,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        execution_timeout: int = 3600,
        is_interactive: bool = False,
        execute_condition: BoolAttr = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: Sequence[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float | None = 5,
        readiness_failure_threshold: int | None = 1,
        readiness_timeout: int | None = 60,
        monitor_readiness: bool = False,
        upstream: Sequence[AnyTask] | AnyTask | None = None,
        fallback: Sequence[AnyTask] | AnyTask | None = None,
        successor: Sequence[AnyTask] | AnyTask | None = None,
        print_fn: PrintFn | None = None,
    ):
        """Define a task that runs a shell command, locally or over SSH.

        Every value below is a literal unless it is a `Tpl` or a callable, in
        which case it is resolved against the task context at run time.

        Args:
            cmd: The command to run. A string, a `Tpl`, a callable taking the
                context, a `Cmd`/`CmdPath`, or a list of any of these joined as
                separate lines.
            cwd: Working directory for the command. Defaults to the process's
                current working directory, i.e. where `zrb` was invoked.
            shell: Shell binary to run under. Defaults to `CFG.SHELL`.
            shell_flag: Flag making the shell read the command, such as `-c`.
                Inferred from `shell` when omitted.
            remote_host: Host to run on over SSH. When omitted the command runs
                locally, and every other `remote_*` value is ignored.
            remote_port: SSH port.
            remote_user: SSH user.
            remote_password: SSH password. Prefer `remote_ssh_key`.
            remote_ssh_key: Path to the private key used for SSH.
            plain_print: When True, stream output verbatim instead of prefixing
                each line with the task name and icon.
            warn_unrecommended_command: Whether to warn about patterns that are
                risky in a non-interactive shell. Defaults to the config setting.
            max_output_line: How many trailing stdout lines to retain in the
                result.
            max_error_line: How many trailing stderr lines to retain in the
                result.
            execution_timeout: Seconds before the command is killed.
            is_interactive: When True, attach the command to the terminal so it can
                prompt. Requires a TTY.

        Every parameter `BaseTask` accepts is also accepted here and behaves
        identically; see `BaseTask` for those.
        """
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
            print_fn=print_fn,
        )
        self._shell = shell
        self._shell_flag = shell_flag
        self._remote_host = remote_host
        self._remote_port = remote_port
        self._remote_user = remote_user
        self._remote_password = remote_password
        self._remote_ssh_key = remote_ssh_key
        self._cmd = cmd
        self._cwd = cwd
        self._max_output_line = max_output_line
        self._max_error_line = max_error_line
        self._execution_timeout = execution_timeout
        self._should_plain_print = plain_print
        self._should_warn_unrecommended_command = warn_unrecommended_command
        self._is_interactive = is_interactive

    async def _exec_action(self, ctx: AnyContext) -> CmdResult:
        """Run the configured command as a subprocess and return its result.

        Args:
            ctx (AnyContext): The task execution context.

        Returns:
            CmdResult: The captured stdout/stderr and exit code.
        """
        cmd_script = self._get_cmd_script(ctx)
        ctx.log_debug(f"Script: {self.__get_multiline_repr(cmd_script)}")
        shell = self._get_shell(ctx)
        ctx.log_debug(f"Shell: {shell}")
        shell_flag = self._get_shell_flag(ctx)
        cwd = self._get_cwd(ctx)
        ctx.log_debug(f"Working directory: {cwd}")
        env_map = self.__get_env_map(ctx)
        # Names kept, credential-looking values masked: DEBUG output is what
        # users paste into bug reports.
        ctx.log_debug(
            f"Environment map: {redact_env_map(env_map, CFG.SECRET_ENV_PATTERNS)}"
        )
        if self._get_should_warn_unrecommended_commands():
            self._check_unrecommended_commands(ctx, shell, cmd_script)
        ctx.log_info("Running script")
        print_method = (
            partial(ctx.print, plain=True) if self._should_plain_print else ctx.print
        )
        xcom_pid_key = f"{self.name}-pid"
        if xcom_pid_key not in ctx.xcom:
            ctx.xcom[xcom_pid_key] = Xcom([])
        cmd_result, return_code = await run_command(
            cmd=[shell, shell_flag, cmd_script],
            cwd=cwd,
            env_map=env_map,
            print_method=print_method,
            register_pid_method=lambda pid: ctx.xcom[xcom_pid_key].push(pid),
            max_output_line=self._max_output_line,
            max_error_line=self._max_error_line,
            timeout=self._execution_timeout,
            is_interactive=self._is_interactive,
        )
        if return_code != 0:
            raise CmdTaskError(self._name, return_code)
        ctx.log_info(f"Exit status: {return_code}")
        return cmd_result

    def _get_should_warn_unrecommended_commands(self):
        if self._should_warn_unrecommended_command is None:
            return CFG.SHOW_UNRECOMMENDED_COMMAND_WARNING
        return self._should_warn_unrecommended_command

    def _check_unrecommended_commands(
        self, ctx: AnyContext, shell: str, cmd_script: str
    ):
        # `get_shell_name`, not `endswith`: on Windows `shell` is an absolute
        # `...\bin\bash.exe` path, and a raw suffix test would silently skip
        # the POSIX lint on the one platform whose default shell is now Git
        # Bash -- i.e. exactly where these warnings matter most.
        if get_shell_name(shell) in ("bash", "zsh"):
            unrecommended_commands = check_unrecommended_commands(cmd_script)
            if unrecommended_commands:
                ctx.log_warning("The script contains unrecommended commands")
            for command, reason in unrecommended_commands.items():
                ctx.log_warning(f"- {command}: {reason}")

    def __get_env_map(self, ctx: AnyContext) -> dict[str, str]:
        envs = {key: val for key, val in ctx.env.items()}
        # SSHPASS must only exist for remote execution: exporting it into the
        # environment of every local command would leak the credential to
        # processes that never need it.
        remote_password = self._get_remote_password(ctx)
        if self._remote_host is not None and remote_password != "":
            envs["SSHPASS"] = remote_password
        envs["PYTHONUNBUFFERED"] = "1"
        return envs

    def _get_shell(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._shell, CFG.SHELL)

    def _get_shell_flag(self, ctx: AnyContext) -> str:
        default_shell_flags = {
            "node": "-e",
            "ruby": "-e",
            "php": "-r",
            "pwsh": "-Command",
            "powershell": "-Command",
            "cmd": "/c",
        }
        default_shell_flag = default_shell_flags.get(
            get_shell_name(self._get_shell(ctx)), "-c"
        )
        return get_str_attr(
            ctx,
            self._shell_flag,
            default_shell_flag,
        )

    def _get_remote_host(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._remote_host, "")

    def _get_remote_port(self, ctx: AnyContext) -> int:
        return get_int_attr(ctx, self._remote_port, 22)

    def _get_remote_user(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._remote_user, "")

    def _get_remote_password(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._remote_password,
            "",
        )

    def _get_remote_ssh_key(self, ctx: AnyContext) -> str:
        return get_str_attr(ctx, self._remote_ssh_key, "")

    def _get_cwd(self, ctx: AnyContext) -> str:
        cwd = get_str_attr(ctx, self._cwd, os.getcwd())
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
            use_password=self._get_remote_password(ctx) != "",
            ssh_key=self._get_remote_ssh_key(ctx),
        )

    def _get_local_cmd_script(self, ctx: AnyContext) -> str:
        return self._resolve_cmd_val(ctx, self._cmd)

    def _resolve_cmd_val(self, ctx: AnyContext, cmd_val: CmdVal) -> str:
        if isinstance(cmd_val, list):
            cmd_val_list = [
                self.__resolve_single_cmd_val(ctx, single_cmd_val)
                for single_cmd_val in cmd_val
            ]
            return "\n".join(
                [cmd_val for cmd_val in cmd_val_list if cmd_val is not None]
            )
        return self.__resolve_single_cmd_val(ctx, cmd_val) or ""

    def __resolve_single_cmd_val(
        self, ctx: AnyContext, single_cmd_val: SingleCmdVal
    ) -> str | None:
        if isinstance(single_cmd_val, AnyCmdVal):
            return single_cmd_val.to_str(ctx)
        if callable(single_cmd_val):
            return single_cmd_val(ctx)
        if isinstance(single_cmd_val, str):
            return single_cmd_val
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
