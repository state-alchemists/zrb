import shlex


def get_remote_cmd_script(
    cmd_script: str,
    host: str = "",
    port: int | str = 22,
    user: str = "",
    use_password: bool = False,
    ssh_key: str = "",
) -> str:
    """Build the `ssh`/`sshpass` invocation that runs `cmd_script` on `host`.

    `use_password` authenticates via `sshpass -e`, which reads the password
    from the `SSHPASS` environment variable — the caller must set that in the
    subprocess environment; the password is never passed on the command line.
    """
    # Quote user-supplied fields — a host, user, port, or key path
    # containing `"`, `` ` `` or `$(…)` would otherwise break out of the
    # double quotes and inject/execute shell. The password is passed via
    # the SSHPASS env var (sshpass -e), not on the command line.
    quoted_script = shlex.quote(cmd_script)
    quoted_port = shlex.quote(str(port))
    quoted_ssh_key = shlex.quote(ssh_key)
    quoted_user_host = shlex.quote(f"{user}@{host}")
    if ssh_key != "" and use_password:
        return f"sshpass -e ssh -t -p {quoted_port} -i {quoted_ssh_key} {quoted_user_host} {quoted_script}"  # noqa
    if ssh_key != "":
        return f"ssh -t -p {quoted_port} -i {quoted_ssh_key} {quoted_user_host} {quoted_script}"  # noqa
    if use_password:
        return f"sshpass -e ssh -t -p {quoted_port} {quoted_user_host} {quoted_script}"  # noqa
    return f"ssh -t -p {quoted_port} {quoted_user_host} {quoted_script}"
