from typing import Any, Mapping
from ruamel.yaml import YAML, CommentedMap


def read_compose_file(file_name: str) -> Any:
    yaml = YAML()
    with open(file_name, 'r') as file:
        data = yaml.load(file)
    return data


def add_services(file_name: str, new_services: Mapping[str, str]):
    yaml = YAML()
    with open(file_name, 'r') as f:
        data = yaml.load(f)
        # data = round_trip_load(f, preserve_quotes=True)
    data = CommentedMap(data)
    data['services'].update(CommentedMap(new_services))
    # Write the modified data structure back to the file
    with open(file_name, 'w') as f:
        yaml.dump(data, f)
        # round_trip_dump(data, f)
