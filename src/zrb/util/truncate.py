from collections.abc import Mapping, Sequence
from typing import Any


def truncate_str(value: Any, limit: int):
    # If value is a string, truncate
    if isinstance(value, str):
        if len(value) > limit:
            if limit < 4:
                return value[:limit]
            return value[: limit - 4] + " ..."
    # If value is a dict, process recursively
    elif isinstance(value, Mapping):
        return {k: truncate_str(v, limit) for k, v in value.items()}
    # If value is a list or tuple, process recursively preserving type
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        t = type(value)
        return t(truncate_str(v, limit) for v in value)
    # If value is a set, process recursively preserving type
    elif isinstance(value, set):
        return {truncate_str(v, limit) for v in value}
    # Other types are returned unchanged
    return value
