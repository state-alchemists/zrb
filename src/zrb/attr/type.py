from typing import Any, Callable

from zrb.context.any_context import AnyContext

fstring = str
AnyAttr = Any | fstring | Callable[[AnyContext], Any]
StrAttr = str | fstring | Callable[[AnyContext], str]
BoolAttr = bool | fstring | Callable[[AnyContext], bool]
IntAttr = int | fstring | Callable[[AnyContext], int]
FloatAttr = float | fstring | Callable[[AnyContext], float]
StrDictAttr = dict[str, StrAttr] | Callable[[AnyContext], dict[str, Any]]
StrListAttr = list[StrAttr] | Callable[[AnyContext], list[str]]
