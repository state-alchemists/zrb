from collections.abc import Mapping
from typing import Any

from ruamel.yaml import YAML, CommentedMap

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.docker_compose.file", attrs=["dark"]))


@typechecked
def read_compose_file(file_name: str) -> Any:
    yaml = YAML()
    with open(file_name, "r") as f:
        data = yaml.load(f)
    return data


@typechecked
def write_compose_file(file_name: str, data: Any):
    yaml = YAML()
    with open(file_name, "w") as f:
        yaml.dump(data, f)


@typechecked
def add_services(file_name: str, new_services: Mapping[str, str]):
    data = read_compose_file(file_name)
    data = CommentedMap(data)
    data["services"].update(CommentedMap(new_services))
    write_compose_file(file_name, data)
