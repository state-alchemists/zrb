"""Deferred-evaluation attribute types.

Each `*Attr` alias accepts the value itself or a callable resolved at run time
against the active context; `zrb.util.attr.get_*_attr` resolves it.

A plain `str` is a literal, never a template; wrap a template in `Tpl`. `Tpl`
renders to text, which the typed getters coerce (`to_boolean`, `int`, ...).

    CmdTask(cmd="echo {literal braces}")        # runs verbatim
    CmdTask(cmd=Tpl("echo {ctx.input.name}"))   # rendered against ctx

There is no `AnyAttr`: `Any | Callable[..., Any]` collapses to `Any`.
"""

from collections.abc import Callable, Sequence
from typing import Any

from zrb.attr.tpl import Tpl

StrAttr = str | Tpl | Callable[..., str | None]
BoolAttr = bool | Tpl | Callable[..., bool | None]
IntAttr = int | Tpl | Callable[..., int | None]
FloatAttr = float | Tpl | Callable[..., float | None]
StrDictAttr = dict[str, StrAttr] | Callable[..., dict[str, Any]]
StrListAttr = Sequence[StrAttr] | Callable[..., list[str]]
