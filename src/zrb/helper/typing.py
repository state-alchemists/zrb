from zrb.config.config import enable_type_checking
from zrb.helper.accessories.untyped_color import untyped_colored as colored
from zrb.helper.log import logger

logger.debug(colored("Loading zrb.helper.typing", attrs=["dark"]))

if enable_type_checking:
    from beartype.typing import (
        Any,
        Callable,
        Iterable,
        List,
        Mapping,
        Optional,
        Tuple,
        Type,
        TypeVar,
        Union,
    )
else:
    from typing import (
        Any,
        Callable,
        Iterable,
        List,
        Mapping,
        Optional,
        Tuple,
        Type,
        TypeVar,
        Union,
    )

JinjaTemplate = str

assert Any
assert Iterable
assert Callable
assert List
assert Mapping
assert Optional
assert TypeVar
assert Type
assert Tuple
assert Union
