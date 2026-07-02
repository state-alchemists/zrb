import shlex


def get_remote_cmd_script(
    cmd_script: str,
    host: str = "",
    port: int | str = 22,
    user: str = "",
    use_password: bool = False,
    ssh_key: str = "",
) -> str:
    """
    Generate an SSH command script to execute a command on a remote host.

    Password authentication uses sshpass -e, which reads the password from
    the SSHPASS environment variable. The caller must set SSHPASS in the
    subprocess environment.

    Args:
        cmd_script (str): The command script to execute on the remote host.
        host (str): The remote host address.
        port (int | str): The SSH port.
        user (str): The SSH user.
        use_password (bool): Whether to use password authentication via sshpass -e.
        ssh_key (str): The path to the SSH private key file.

    Returns:
        str: The generated SSH command script.
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
