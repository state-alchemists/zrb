from typing import Any, List


def append_unique(data: List[Any], *new_data: Any) -> List[Any]:
    for new_datum in new_data:
        if new_datum in data:
            continue
        data.append(new_datum)
    return data
