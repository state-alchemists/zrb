from typing import TypeVar

from zrb.config.config import ENABLE_TYPE_CHECKING
from zrb.helper.accessories.untyped_color import untyped_colored as colored
from zrb.helper.log import logger

logger.debug(colored("Loading zrb.helper.typecheck", attrs=["dark"]))
T = TypeVar("T")


def typechecked(anything: T) -> T:
    if ENABLE_TYPE_CHECKING:
        from beartype import beartype

        return beartype(anything)
    return anything
