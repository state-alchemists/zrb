from typing import Unpack

from zrb.attr.type import StrAttr
from zrb.context.any_context import AnyContext
from zrb.task.base.params import CmdTaskParams, reject_non_rsync_params
from zrb.task.cmd_task import CmdTask
from zrb.util.attr import get_str_attr


class RsyncTask(CmdTask):
    def __init__(
        self,
        name: str,
        *,
        remote_source_path: StrAttr | None = None,
        remote_destination_path: StrAttr | None = None,
        local_source_path: StrAttr | None = None,
        local_destination_path: StrAttr | None = None,
        exclude_from: StrAttr | None = None,
        **kwargs: Unpack[CmdTaskParams],
    ):
        """Define a task that copies files with `rsync`, locally or over SSH.

        Exactly one side may be remote. Pair `local_source_path` with
        `remote_destination_path` to upload, or `remote_source_path` with
        `local_destination_path` to download. The SSH connection reuses `CmdTask`'s
        `remote_*` parameters.

        Every value below is a literal unless it is a `Tpl` or a callable, in
        which case it is resolved against the task context at run time.

        Args:
            local_source_path: Path on this machine to copy from.
            local_destination_path: Path on this machine to copy to.
            remote_source_path: Path on the remote host to copy from.
            remote_destination_path: Path on the remote host to copy to.
            exclude_from: Path to a file listing rsync exclude patterns, passed
                through as `--exclude-from`.

        Every parameter `CmdTask` accepts is also accepted here **except
        `cmd` and `warn_unrecommended_command`** — the command is generated
        from the paths above, so neither is meaningful. The rest behaves
        identically, except for the two that only make sense for a
        user-supplied command: `cmd`, which is generated here from the paths
        above, and `warn_unrecommended_command`, which screens a command you
        wrote.
        """
        reject_non_rsync_params("RsyncTask", dict(kwargs))
        super().__init__(
            name=name,
            **kwargs,
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
