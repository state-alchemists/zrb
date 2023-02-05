from typing import Any, Mapping
from ..dynamic_model import DynamicModel


def get_object_from_keyval(map: Mapping[str, Any]) -> DynamicModel:
    return DynamicModel(**map)
