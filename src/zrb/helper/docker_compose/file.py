from ruamel.yaml import YAML, CommentedMap

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Mapping


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
