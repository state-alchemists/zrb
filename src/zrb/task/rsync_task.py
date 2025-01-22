from collections.abc import Callable

from zrb.attr.type import IntAttr, StrAttr
from zrb.context.any_context import AnyContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask
from zrb.task.cmd_task import CmdTask
from zrb.util.attr import get_str_attr


class RsyncTask(CmdTask):
    def __init__(
        self,
        name: str,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: list[AnyInput] | AnyInput | None = None,
        env: list[AnyEnv] | AnyEnv | None = None,
        shell: StrAttr | None = None,
        auto_render_shell: bool = True,
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
        remote_source_path: StrAttr | None = None,
        render_remote_source_path: bool = True,
        remote_destination_path: StrAttr | None = None,
        render_remote_destination_path: bool = True,
        local_source_path: StrAttr | None = None,
        render_local_source_path: bool = True,
        local_destination_path: StrAttr | None = None,
        render_local_destination_path: bool = True,
        cwd: str | None = None,
        render_cwd: bool = True,
        plain_print: bool = False,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        execute_condition: bool | str | Callable[[AnyContext], bool] = True,
        retries: int = 2,
        retry_period: float = 0,
        readiness_check: list[AnyTask] | AnyTask | None = None,
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
            shell=shell,
            render_shell=auto_render_shell,
            remote_host=remote_host,
            render_remote_host=render_remote_host,
            remote_port=remote_port,
            auto_render_remote_port=render_remote_port,
            remote_user=remote_user,
            render_remote_user=render_remote_user,
            remote_password=remote_password,
            render_remote_password=render_remote_password,
            remote_ssh_key=remote_ssh_key,
            render_remote_ssh_key=render_remote_ssh_key,
            cwd=cwd,
            render_cwd=render_cwd,
            plain_print=plain_print,
            max_output_line=max_output_line,
            max_error_line=max_error_line,
            execute_condition=execute_condition,
            retries=retries,
            retry_period=retry_period,
            readiness_check=readiness_check,
            upstream=upstream,
            fallback=fallback,
            successor=successor,
        )
        self._remote_source_path = remote_source_path
        self._render_remote_source_path = render_remote_source_path
        self._remote_destination_path = remote_destination_path
        self._render_remote_destination_path = render_remote_destination_path
        self._local_source_path = local_source_path
        self._render_local_source_path = render_local_source_path
        self._local_destination_path = local_destination_path
        self._render_local_destination_path = render_local_destination_path

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
            auto_render=self._render_remote_source_path,
        )

    def _get_remote_destination_path(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._remote_destination_path,
            "",
            auto_render=self._render_remote_destination_path,
        )

    def _get_local_source_path(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._local_source_path,
            "",
            auto_render=self._render_local_source_path,
        )

    def _get_local_destination_path(self, ctx: AnyContext) -> str:
        return get_str_attr(
            ctx,
            self._local_destination_path,
            "",
            auto_render=self._render_local_destination_path,
        )

    def _get_cmd_script(self, ctx: AnyContext) -> str:
        port = self._get_remote_port(ctx)
        password = self._get_remote_password(ctx)
        key = self._get_remote_ssh_key(ctx)
        src = self._get_source_path(ctx)
        dst = self._get_destination_path(ctx)
        if key != "" and password != "":
            return f'sshpass -p "$_ZRB_SSH_PASSWORD" rsync --mkpath -avz -e "ssh -i {key} -p {port}" {src} {dst}'  # noqa
        if key != "":
            return f'rsync --mkpath -avz -e "ssh -i {key} -p {port}" {src} {dst}'
        if password != "":
            return f'sshpass -p "$_ZRB_SSH_PASSWORD" rsync --mkpath -avz -e "ssh -p {port}" {src} {dst}'  # noqa
        return f'rsync --mkpath -avz -e "ssh -p {port}" {src} {dst}'
