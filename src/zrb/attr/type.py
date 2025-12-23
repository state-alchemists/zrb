from typing import Any, Callable

from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext

fstring = str
AnyAttr = Any | fstring | Callable[[AnyContext | AnySharedContext], Any]
StrAttr = str | fstring | Callable[[AnyContext | AnySharedContext], str | None]
BoolAttr = bool | fstring | Callable[[AnyContext | AnySharedContext], bool | None]
IntAttr = int | fstring | Callable[[AnyContext | AnySharedContext], int | None]
FloatAttr = float | fstring | Callable[[AnyContext | AnySharedContext], float | None]
StrDictAttr = (
    dict[str, StrAttr] | Callable[[AnyContext | AnySharedContext], dict[str, Any]]
)
StrListAttr = list[StrAttr] | Callable[[AnyContext | AnySharedContext], list[str]]
