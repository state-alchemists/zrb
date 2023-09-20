from typing import TypeVar
from zrb.helper.string.constant import FALSE_STRS
from beartype import beartype
import os

enable_type_checking_str = os.getenv('ZRB_ENABLE_TYPE_CHECKING', '1').lower()
enable_type_checking = enable_type_checking_str not in FALSE_STRS

T = TypeVar('T')


def typechecked(anything: T) -> T:
    if enable_type_checking:
        return beartype(anything)
    return anything
