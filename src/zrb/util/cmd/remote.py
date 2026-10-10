import os
import shlex


def get_remote_cmd_script(
    cmd_script: str,
    host: str = "",
    port: int | str = 22,
    user: str = "",
    use_password: bool = False,
    ssh_key: str = "",
    tty: bool = True,
) -> str:
    """Build the `ssh`/`sshpass` invocation that runs `cmd_script` on `host`.

    `use_password` uses `sshpass -e`: the caller must set `SSHPASS` in the
    subprocess environment. A leading `~` in `ssh_key` is expanded. `tty=False`
    passes `-T` instead of `-t`, for non-interactive commands on servers that
    refuse a pseudo-terminal (`PermitTTY no`).
    """
    # Quoted to prevent shell injection through user-supplied fields.
    parts = ["sshpass -e ssh" if use_password else "ssh", "-t" if tty else "-T"]
    parts += ["-p", shlex.quote(str(port))]
    if ssh_key != "":
        parts += ["-i", shlex.quote(os.path.expanduser(ssh_key))]
    parts.append(shlex.quote(f"{user}@{host}" if user else host))
    parts.append(shlex.quote(cmd_script))
    return " ".join(parts)
