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
    quoted_script = shlex.quote(cmd_script)
    if ssh_key != "" and use_password:
        return f'sshpass -p "{password}" ssh -t -p "{port}" -i "{ssh_key}" "{user}@{host}" {quoted_script}'  # noqa
    if ssh_key != "":
        return f'ssh -t -p "{port}" -i "{ssh_key}" "{user}@{host}" {quoted_script}'
    if use_password:
        return f'sshpass -p "{password}" ssh -t -p "{port}" "{user}@{host}" {quoted_script}'  # noqa
    return f'ssh -t -p "{port}" "{user}@{host}" {quoted_script}'
