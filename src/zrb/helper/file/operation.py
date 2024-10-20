import shlex
import subprocess

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.ssh import get_remote_cmd_script
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.file.operation", attrs=["dark"]))


@typechecked
def read_remote_file(
    file_path: str,
    host: str = "",
    port: int = 22,
    user: str = "",
    password: str = "",
    use_password: bool = False,
    ssh_key: str = "",
) -> str:
    remote_cmd_script = get_remote_cmd_script(
        cmd_script=f'cat "{file_path}"',
        host=host,
        port=port,
        user=user,
        password=password,
        use_password=use_password,
        ssh_key=ssh_key,
    )
    # Use SSH to read the remote file
    result = subprocess.run(
        remote_cmd_script, shell=True, capture_output=True, text=True, check=True
    )
    return result.stdout


@typechecked
def read_local_file(file_path: str) -> str:
    with open(file_path, "r") as file:
        return file.read()


@typechecked
def write_remote_file(
    file_path: str,
    content: str,
    host: str = "",
    port: int = 22,
    user: str = "",
    password: str = "",
    use_password: bool = False,
    ssh_key: str = "",
) -> str:
    remote_cmd_script = get_remote_cmd_script(
        cmd_script=f'echo {shlex.quote(content)} > "{file_path}"',
        host=host,
        port=port,
        user=user,
        password=password,
        use_password=use_password,
        ssh_key=ssh_key,
    )
    # Use SSH to read the remote file
    subprocess.run(
        remote_cmd_script, shell=True, capture_output=True, text=True, check=True
    )


@typechecked
def write_local_file(file_path: str, content: str):
    with open(file_path, "w") as file:
        file.write(content)


@typechecked
def is_remote_file_exists(
    file_path: str,
    host: str = "",
    port: int = 22,
    user: str = "",
    password: str = "",
    use_password: bool = False,
    ssh_key: str = "",
) -> bool:
    # Build the remote command to check if the file exists
    remote_cmd_script = get_remote_cmd_script(
        cmd_script=f'test -f "{file_path}" && echo "exists" || echo "not_found"',
        host=host,
        port=port,
        user=user,
        password=password,
        use_password=use_password,
        ssh_key=ssh_key,
    )
    # Execute the command remotely
    result = subprocess.run(
        remote_cmd_script, shell=True, capture_output=True, text=True, check=True
    )
    return "exists" in result.stdout.strip()
