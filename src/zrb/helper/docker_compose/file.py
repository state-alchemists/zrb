from collections.abc import Mapping
from typing import Any

from io import StringIO
from ruamel.yaml import YAML, CommentedMap

from zrb.helper.accessories.color import colored
from zrb.helper.file.operation import read_remote_file, write_remote_file
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.docker_compose.file", attrs=["dark"]))


@typechecked
def read_local_compose_file(file_path: str) -> Any:
    yaml = YAML()
    with open(file_path, "r") as f:
        data = yaml.load(f)
    return data


@typechecked
def write_local_compose_file(file_path: str, data: Any):
    yaml = YAML()
    with open(file_path, "w") as f:
        yaml.dump(data, f)


@typechecked
def add_services_to_local_compose_file(file_path: str, new_services: Mapping[str, str]):
    data = read_local_compose_file(file_path)
    data = CommentedMap(data)
    data["services"].update(CommentedMap(new_services))
    write_local_compose_file(file_path, data)


@typechecked
def read_remote_compose_file(
    file_path: str,
    host: str = "",
    port: int = 22,
    user: str = "",
    password: str = "",
    use_password: bool = False,
    ssh_key: str = "",
) -> Any:
    content = read_remote_file(
        file_path=file_path,
        host=host,
        port=port,
        user=user,
        password=password,
        use_password=use_password,
        ssh_key=ssh_key
    )
    yaml = YAML()
    return yaml.load(content)


@typechecked
def write_remote_compose_file(
    file_path: str,
    data: Any,
    host: str = "",
    port: int = 22,
    user: str = "",
    password: str = "",
    use_password: bool = False,
    ssh_key: str = "",
):
    output_stream = StringIO()
    yaml = YAML()
    yaml.dump(data, output_stream)
    content = output_stream.getvalue()
    write_remote_file(
        file_path=file_path,
        content=content,
        host=host,
        port=port,
        user=user,
        password=password,
        use_password=use_password,
        ssh_key=ssh_key
    )


@typechecked
def add_services_to_remote_compose_file(
    file_path: str,
    new_services: Mapping[str, str],
    host: str = "",
    port: int = 22,
    user: str = "",
    password: str = "",
    use_password: bool = False,
    ssh_key: str = "",

):
    data = read_remote_compose_file(
        file_path=file_path,
        host=host,
        port=port,
        user=user,
        password=password,
        use_password=use_password,
        ssh_key=ssh_key
    )
    data = CommentedMap(data)
    data["services"].update(CommentedMap(new_services))
    write_remote_compose_file(
        file_path=file_path,
        data=data,
        host=host,
        port=port,
        user=user,
        password=password,
        use_password=use_password,
        ssh_key=ssh_key
    )
