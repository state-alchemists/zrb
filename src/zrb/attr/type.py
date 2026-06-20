from collections.abc import Sequence
from typing import Any, Callable

fstring = str
AnyAttr = Any | fstring | Callable[..., Any]
StrAttr = str | fstring | Callable[..., str | None]
BoolAttr = bool | fstring | Callable[..., bool | None]
IntAttr = int | fstring | Callable[..., int | None]
FloatAttr = float | fstring | Callable[..., float | None]
StrDictAttr = dict[str, StrAttr] | Callable[..., dict[str, Any]]
StrListAttr = Sequence[StrAttr] | Callable[..., list[str]]
