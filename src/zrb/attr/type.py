from typing import Any, Callable

from zrb.context.any_shared_context import AnySharedContext

fstring = str
AnyAttr = Any | fstring | Callable[[AnySharedContext], Any]
StrAttr = str | fstring | Callable[[AnySharedContext], str]
BoolAttr = bool | fstring | Callable[[AnySharedContext], bool]
IntAttr = int | fstring | Callable[[AnySharedContext], int]
FloatAttr = float | fstring | Callable[[AnySharedContext], float]
StrDictAttr = dict[str, StrAttr] | Callable[[AnySharedContext], dict[str, Any]]
StrListAttr = list[StrAttr] | Callable[[AnySharedContext], list[str]]
