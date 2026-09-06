"""Deferred-evaluation attribute types.

Every `*Attr` alias says the same thing: this parameter accepts the value
itself, or a callable resolved at run time against the active context.
`zrb.util.attr.get_*_attr` is what collapses the two into a concrete value.

**A plain `str` is a literal, never a template.** Rendering is opt-in: wrap a
template in `Tpl`, which every alias names explicitly. `Tpl` renders to *text*,
so it is listed alongside `bool`/`int`/`float` rather than folded into their
`Callable[..., bool | None]` arms — the typed getter coerces the rendered
string (`get_bool_attr` via `to_boolean`, `get_int_attr` via `int`).

    CmdTask(cmd="echo {literal braces}")        # runs verbatim
    CmdTask(cmd=Tpl("echo {ctx.input.name}"))   # rendered against ctx

There is deliberately no `AnyAttr`: `Any | Callable[..., Any]` collapses to
plain `Any`, so it would constrain nothing while looking like it did. Use
`Any` where anything goes, or the specific `*Attr` alias where it does not.
"""

from collections.abc import Sequence
from typing import Any, Callable

from zrb.attr.tpl import Tpl

StrAttr = str | Tpl | Callable[..., str | None]
BoolAttr = bool | Tpl | Callable[..., bool | None]
IntAttr = int | Tpl | Callable[..., int | None]
FloatAttr = float | Tpl | Callable[..., float | None]
StrDictAttr = dict[str, StrAttr] | Callable[..., dict[str, Any]]
StrListAttr = Sequence[StrAttr] | Callable[..., list[str]]
