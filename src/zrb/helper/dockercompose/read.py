from typing import Any
from ruamel.yaml import YAML


def read_file(file_name: str) -> Any:
    yaml = YAML()
    with open(file_name, 'r') as f:
        data = yaml.load(f)
    return data
