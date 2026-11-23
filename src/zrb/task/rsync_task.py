import shlex
from typing import Unpack

from zrb.attr.type import StrAttr
from zrb.cmd.remote import bracket_ipv6
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

        At most one side may be remote: pair `local_source_path` with
        `remote_destination_path` to upload, `remote_source_path` with
        `local_destination_path` to download, or two local paths to sync
        locally. Two remote sides, or a side that sets both its local and
        remote path, are refused before anything runs; a remote side requires
        `remote_host`. The SSH connection reuses `CmdTask`'s `remote_*`
        parameters.

        Every value below is a literal unless it is a `Tpl` or a callable, in
        which case it is resolved against the task context at run time.

        Args:
            local_source_path: Path on this machine to copy from.
            local_destination_path: Path on this machine to copy to.
            remote_source_path: Path on the remote host to copy from.
            remote_destination_path: Path on the remote host to copy to.
            exclude_from: Path to a file listing rsync exclude patterns, passed
                through as `--exclude-from`.

        Every other parameter is `CmdTask`'s, except `cmd` and
        `warn_unrecommended_command`, since the command is generated.
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
        return self._get_remote_path(ctx, self._get_remote_source_path(ctx))

    def _get_destination_path(self, ctx: AnyContext) -> str:
        local_destination_path = self._get_local_destination_path(ctx)
        if local_destination_path != "":
            return local_destination_path
        return self._get_remote_path(ctx, self._get_remote_destination_path(ctx))

    def _get_remote_path(self, ctx: AnyContext, path: str) -> str:
        user = self._get_remote_user(ctx)
        user_prefix = f"{user}@" if user != "" else ""
        return f"{user_prefix}{bracket_ipv6(self._get_remote_host(ctx))}:{path}"

    def _validate_paths(self, ctx: AnyContext) -> None:
        """Refuse a path combination `rsync` cannot run as configured.

        Each side must name exactly one path; two remote sides are refused,
        while two local sides are a valid local copy. A remote side also
        requires `remote_host`. Runs before the command is built, so a bad
        pair never reaches the shell.
        """
        source_is_remote = self._side_is_remote(
            "source",
            self._get_local_source_path(ctx),
            self._get_remote_source_path(ctx),
        )
        destination_is_remote = self._side_is_remote(
            "destination",
            self._get_local_destination_path(ctx),
            self._get_remote_destination_path(ctx),
        )
        if source_is_remote and destination_is_remote:
            raise ValueError(
                f"RsyncTask({self.name!r}) cannot run remote-to-remote: at "
                "most one of the source and destination may be remote."
            )
        if (source_is_remote or destination_is_remote) and (
            self._get_remote_host(ctx) == ""
        ):
            raise ValueError(
                f"RsyncTask({self.name!r}) has a remote path but no "
                "remote_host; set remote_host to the SSH server."
            )

    def _side_is_remote(self, side: str, local: str, remote: str) -> bool:
        if local != "" and remote != "":
            raise ValueError(
                f"RsyncTask({self.name!r}) sets both local_{side}_path and "
                f"remote_{side}_path; set exactly one."
            )
        if local != "":
            return False
        if remote != "":
            return True
        raise ValueError(
            f"RsyncTask({self.name!r}) needs either local_{side}_path or "
            f"remote_{side}_path."
        )

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
        return shlex.quote(f"--exclude-from={exclude_from}")

    def _get_ssh_command(self, ctx: AnyContext) -> str:
        """The `ssh` command for rsync's `-e`, quoted for both shells.

        `shlex.quote(key)` protects the key inside the command rsync runs;
        quoting the whole string then protects it from the parent shell.
        """
        port = self._get_remote_port(ctx)
        key = self._get_remote_ssh_key(ctx)
        parts = ["ssh"]
        if key != "":
            parts += ["-i", shlex.quote(key)]
        parts += ["-p", shlex.quote(str(port))]
        return shlex.quote(" ".join(parts))

    def _get_cmd_script(self, ctx: AnyContext) -> str:
        self._validate_paths(ctx)
        password = self._get_remote_password(ctx)
        ssh_command = self._get_ssh_command(ctx)
        exclude_from = self._get_exclude_from_param(ctx)
        exclude_from_with_space = f"{exclude_from} " if exclude_from != "" else ""
        src = shlex.quote(self._get_source_path(ctx))
        dst = shlex.quote(self._get_destination_path(ctx))
        sshpass = "sshpass -e " if password != "" else ""
        return (
            f"{sshpass}rsync --mkpath -avz -e {ssh_command} "
            f"{exclude_from_with_space}{src} {dst}"
        )
