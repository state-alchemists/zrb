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

    `use_password` uses `sshpass -e`: the caller must set `SSHPASS` in the
    subprocess environment.
    """
    # Quoted to prevent shell injection through user-supplied fields.
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
