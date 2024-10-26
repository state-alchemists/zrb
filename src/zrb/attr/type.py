from typing import Any, Callable
from ..context.any_shared_context import AnySharedContext

AnyAttr = Any | Callable[[AnySharedContext], Any]
StrAttr = str | Callable[[AnySharedContext], str]
BoolAttr = bool | str | Callable[[AnySharedContext], bool]
IntAttr = int | str | Callable[[AnySharedContext], int]
FloatAttr = float | str | Callable[[AnySharedContext], float]
