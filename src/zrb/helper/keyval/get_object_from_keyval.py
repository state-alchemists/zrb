from typing import Any, Mapping


class DynamicModel:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self) -> str:
        return str(self.__dict__)


def get_object_from_keyval(map: Mapping[str, Any]) -> DynamicModel:
    return DynamicModel(**map)
