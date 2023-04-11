from typing import Any, Iterable, List


def reverse(data: Iterable[Any]) -> List[Any]:
    new_data = list(data)
    new_data.reverse()
    return new_data
