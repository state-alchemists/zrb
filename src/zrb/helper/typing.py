from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional, Type, TypeVar, Union

from zrb.helper.accessories.untyped_color import untyped_colored as colored
from zrb.helper.log import logger

logger.debug(colored("Loading zrb.helper.typing", attrs=["dark"]))

Tuple = tuple
List = list

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
