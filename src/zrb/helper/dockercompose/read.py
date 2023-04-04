from typing import Any
from ruamel.yaml import YAML


def read_compose_file(file_name: str) -> Any:
    yaml = YAML()
    with open(file_name, 'r') as file:
        data = yaml.load(file)
    return data
