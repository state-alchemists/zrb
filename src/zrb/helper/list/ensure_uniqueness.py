from typing import Any, Callable, List, Optional

TComparator = Callable[[Any, Any], bool]


def ensure_uniqueness(
    data: List[Any], comparator: Optional[TComparator] = None
) -> List[Any]:
    unique_data = []
    for datum in data:
        if datum in unique_data:
            continue
        if comparator is not None:
            is_exist = False
            for unique_datum in unique_data:
                if comparator(unique_datum, datum):
                    is_exist = True
                    break
            if is_exist:
                continue
        unique_data.append(datum)
    return unique_data
