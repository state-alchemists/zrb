from typing import Any, Callable

from zrb.context.any_context import AnyContext

fstring = str
AnyAttr = Any | fstring | Callable[[AnyContext], Any]
StrAttr = str | fstring | Callable[[AnyContext], str | None]
BoolAttr = bool | fstring | Callable[[AnyContext], bool | None]
IntAttr = int | fstring | Callable[[AnyContext], int | None]
FloatAttr = float | fstring | Callable[[AnyContext], float | None]
StrDictAttr = dict[str, StrAttr] | Callable[[AnyContext], dict[str, Any]]
StrListAttr = list[StrAttr] | Callable[[AnyContext], list[str]]
