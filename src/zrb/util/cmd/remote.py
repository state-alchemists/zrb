import shlex


def get_remote_cmd_script(
    cmd_script: str,
    host: str = "",
    port: int | str = 22,
    user: str = "",
    password: str = "",
    use_password: bool = False,
    ssh_key: str = "",
) -> str:
    """
    Generate an SSH command script to execute a command on a remote host.

    Args:
        cmd_script (str): The command script to execute on the remote host.
        host (str): The remote host address.
        port (int | str): The SSH port.
        user (str): The SSH user.
        password (str): The SSH password (used with sshpass if use_password is True).
        use_password (bool): Whether to use password authentication with sshpass.
        ssh_key (str): The path to the SSH private key file.

    Returns:
        str: The generated SSH command script.
    """
    quoted_script = shlex.quote(cmd_script)
    if ssh_key != "" and use_password:
        return f'sshpass -p "{password}" ssh -t -p "{port}" -i "{ssh_key}" "{user}@{host}" {quoted_script}'  # noqa
    if ssh_key != "":
        return f'ssh -t -p "{port}" -i "{ssh_key}" "{user}@{host}" {quoted_script}'
    if use_password:
        return f'sshpass -p "{password}" ssh -t -p "{port}" "{user}@{host}" {quoted_script}'  # noqa
    return f'ssh -t -p "{port}" "{user}@{host}" {quoted_script}'
