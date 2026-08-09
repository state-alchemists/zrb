"""Deferred-evaluation attribute types.

Every `*Attr` alias says the same thing: this parameter accepts the value
itself, a string template rendered against the active context, or a callable
resolved at run time. `zrb.util.attr.get_*_attr` is what collapses the three
into a concrete value.

`fstring` is an alias for `str`, not a distinct type — the type checker sees
`str` and always will. It earns its place as *documentation*: in
`BoolAttr = bool | fstring | ...` it says "or a template string that renders to
a bool", which `str` alone does not. It is deliberately not a `NewType`, since
that would reject the plain string literals every call site passes.

There is deliberately no `AnyAttr`: `Any | fstring | Callable[..., Any]`
collapses to plain `Any`, so it would constrain nothing while looking like it
did. Use `Any` where anything goes, or the specific `*Attr` alias where it does
not.
"""

from collections.abc import Sequence
from typing import Any, Callable

fstring = str
StrAttr = str | fstring | Callable[..., str | None]
BoolAttr = bool | fstring | Callable[..., bool | None]
IntAttr = int | fstring | Callable[..., int | None]
FloatAttr = float | fstring | Callable[..., float | None]
StrDictAttr = dict[str, StrAttr] | Callable[..., dict[str, Any]]
StrListAttr = Sequence[StrAttr] | Callable[..., list[str]]
