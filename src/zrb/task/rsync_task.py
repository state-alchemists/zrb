from collections.abc import Sequence

from zrb.attr.type import BoolAttr, IntAttr, StrAttr
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.cmd_task import CmdTask
from zrb.util.attr import get_str_attr


class RsyncTask(CmdTask):
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
        is_interactive: bool = False,
        remote_host: StrAttr | None = None,
        remote_port: IntAttr | None = None,
        remote_user: StrAttr | None = None,
        remote_password: StrAttr | None = None,
        remote_ssh_key: StrAttr | None = None,
        remote_source_path: StrAttr | None = None,
        remote_destination_path: StrAttr | None = None,
        local_source_path: StrAttr | None = None,
        local_destination_path: StrAttr | None = None,
        exclude_from: StrAttr | None = None,
        cwd: str | None = None,
        plain_print: bool = False,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        execution_timeout: int = 3600,
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
        """Define a task that copies files with `rsync`, locally or over SSH.

        Exactly one side may be remote. Pair `local_source_path` with
        `remote_destination_path` to upload, or `remote_source_path` with
        `local_destination_path` to download. The SSH connection reuses `CmdTask`'s
        `remote_*` parameters.

        A `render_x` flag controls whether `x` is treated as an f-string template
        rendered against the task context. Set it False to pass a literal value
        containing braces.

        Args:
            local_source_path: Path on this machine to copy from.
            local_destination_path: Path on this machine to copy to.
            remote_source_path: Path on the remote host to copy from.
            remote_destination_path: Path on the remote host to copy to.
            exclude_from: Path to a file listing rsync exclude patterns, passed
                through as `--exclude-from`.

        Every parameter `CmdTask` accepts is also accepted here and behaves
        identically, except for the three that only make sense for a
        user-supplied command: `cmd` and `render_cmd`, which are generated here
        from the paths above, and `warn_unrecommended_command`, which screens a
        command you wrote.
        """
        super().__init__(
            name=name,
            color=color,
            icon=icon,
            description=description,
            cli_only=cli_only,
            input=input,
            env=env,
            shell=shell,
            shell_flag=shell_flag,
            is_interactive=is_interactive,
            remote_host=remote_host,
            remote_port=remote_port,
            remote_user=remote_user,
            remote_password=remote_password,
            remote_ssh_key=remote_ssh_key,
            cwd=cwd,
            plain_print=plain_print,
            max_output_line=max_output_line,
            max_error_line=max_error_line,
            execution_timeout=execution_timeout,
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
        self._remote_source_path = remote_source_path
        self._remote_destination_path = remote_destination_path
        self._local_source_path = local_source_path
        self._local_destination_path = local_destination_path
        self._exclude_from = exclude_from

    def _get_source_path(self, ctx: AnyContext) -> str:
        local_source_path = self._get_local_source_path(ctx)
        if local_source_path != "":
            return local_source_path
        remote_source_path = self._get_remote_source_path(ctx)
        host = self._get_remote_host(ctx)
        user = self._get_remote_user(ctx)
        return f"{user}@{host}:{remote_source_path}"

    def _get_destination_path(self, ctx: AnyContext) -> str:
        local_destination_path = self._get_local_destination_path(ctx)
        if local_destination_path != "":
            return local_destination_path
        remote_destination_path = self._get_remote_destination_path(ctx)
        host = self._get_remote_host(ctx)
        user = self._get_remote_user(ctx)
        return f"{user}@{host}:{remote_destination_path}"

    def _get_remote_source_path(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._remote_source_path,
            "",
        )

    def _get_remote_destination_path(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._remote_destination_path,
            "",
        )

    def _get_local_source_path(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._local_source_path,
            "",
        )

    def _get_local_destination_path(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._local_destination_path,
            "",
        )

    def _get_exclude_from_param(self, ctx: AnyContext) -> str:
        exclude_from = get_str_attr(
            ctx,
            self._exclude_from,
            "",
        ).strip()
        if exclude_from == "":
            return ""
        return f"--exclude-from='{exclude_from}'"

    def _get_cmd_script(self, ctx: AnyContext) -> str:
        port = self._get_remote_port(ctx)
        password = self._get_remote_password(ctx)
        key = self._get_remote_ssh_key(ctx)
        src = self._get_source_path(ctx)
        dst = self._get_destination_path(ctx)
        exclude_from = self._get_exclude_from_param(ctx)
        exclude_from_with_space = f"{exclude_from} " if exclude_from != "" else ""
        if key != "" and password != "":
            return f'sshpass -e rsync --mkpath -avz -e "ssh -i {key} -p {port}" {exclude_from_with_space}{src} {dst}'  # noqa
        if key != "":
            return f'rsync --mkpath -avz -e "ssh -i {key} -p {port}" {exclude_from_with_space}{src} {dst}'  # noqa
        if password != "":
            return f'sshpass -e rsync --mkpath -avz -e "ssh -p {port}" {exclude_from_with_space}{src} {dst}'  # noqa
        return f'rsync --mkpath -avz -e "ssh -p {port}" {exclude_from_with_space}{src} {dst}'
