from typing import Any
from zrb.helper.string.constant import FALSE_STRS
from beartype import beartype
import os

enable_type_checking_str = os.getenv('ZRB_ENABLE_TYPE_CHECKING', '1').lower()
enable_type_checking = enable_type_checking_str not in FALSE_STRS


def typechecked(anything: Any) -> Any:
    if enable_type_checking:
        return beartype(anything)
    return anything
