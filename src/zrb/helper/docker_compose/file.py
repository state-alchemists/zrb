from typing import Any, Mapping
from ruamel.yaml import YAML, CommentedMap


def read_compose_file(file_name: str) -> Any:
    yaml = YAML()
    with open(file_name, 'r') as f:
        data = yaml.load(f)
    return data


def write_compose_file(file_name: str, data: Any):
    yaml = YAML()
    with open(file_name, 'w') as f:
        yaml.dump(data, f)


def add_services(file_name: str, new_services: Mapping[str, str]):
    data = read_compose_file(file_name)
    data = CommentedMap(data)
    data['services'].update(CommentedMap(new_services))
    write_compose_file(file_name, data)
