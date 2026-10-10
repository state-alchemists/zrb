import shlex


def bracket_ipv6(host: str) -> str:
    """Wrap an IPv6 literal in brackets, as URLs and `rsync` paths require.

    A bracketed host, a DNS name and an IPv4 address are returned unchanged.
    """
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


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
    subprocess environment. `tty=False`
    passes `-T` instead of `-t`, for non-interactive commands on servers that
    refuse a pseudo-terminal (`PermitTTY no`).
    """
    # Quoted to prevent shell injection through user-supplied fields.
    parts = ["sshpass -e ssh" if use_password else "ssh", "-t" if tty else "-T"]
    parts += ["-p", shlex.quote(str(port))]
    if ssh_key != "":
        parts += ["-i", shlex.quote(ssh_key)]
    parts.append(shlex.quote(f"{user}@{host}" if user else host))
    parts.append(shlex.quote(cmd_script))
    return " ".join(parts)
