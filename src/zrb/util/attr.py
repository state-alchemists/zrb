from typing import Any

from zrb.attr.type import (
    BoolAttr,
    FloatAttr,
    IntAttr,
    StrAttr,
    StrDictAttr,
    StrListAttr,
)
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.util.string.conversion import to_boolean


def get_str_list_attr(
    ctx: AnyContext | AnySharedContext,
    attr: StrListAttr | None,
) -> list[str]:
    """Resolve a `StrListAttr` — `None`, a list of literals or `Tpl`/callables,
    or a callable taking `ctx` — to a plain `list[str]`."""
    if attr is None:
        return []
    if callable(attr):
        return attr(ctx)
    return [get_str_attr(ctx, val, "") for val in attr]


def get_str_dict_attr(
    ctx: AnyContext | AnySharedContext,
    attr: StrDictAttr | None,
) -> dict[str, Any]:
    """Resolve a `StrDictAttr` — `None`, a dict of literals or `Tpl`/callables,
    or a callable taking `ctx` — to a plain `dict[str, Any]`."""
    if attr is None:
        return {}
    if callable(attr):
        return attr(ctx)
    return {key: get_str_attr(ctx, val, "") for key, val in attr.items()}


def get_str_attr(
    ctx: AnyContext | AnySharedContext,
    attr: StrAttr | None,
    default: StrAttr = "",
) -> str:
    """Resolve a `StrAttr` to a plain `str`, falling back to `default` (itself
    resolved the same way) when `attr` is `None`."""
    val = get_attr(ctx, attr, default)
    if isinstance(val, str):
        return val
    if val is None:
        return ""
    return str(val)


def get_bool_attr(
    ctx: AnyContext | AnySharedContext,
    attr: BoolAttr | None,
    default: BoolAttr = False,
) -> bool:
    """Resolve a `BoolAttr` to a plain `bool`, falling back to `default`
    (itself resolved the same way) when `attr` is `None`."""
    val = get_attr(ctx, attr, default)
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return to_boolean(val)


def get_int_attr(
    ctx: AnyContext | AnySharedContext,
    attr: IntAttr | None,
    default: IntAttr = 0,
) -> int:
    """Resolve an `IntAttr` to a plain `int`, falling back to `default`
    (itself resolved the same way) when `attr` is `None`."""
    val = get_attr(ctx, attr, default)
    if isinstance(val, int):
        return val
    if val is None:
        return 0
    return int(val)


def get_float_attr(
    ctx: AnyContext | AnySharedContext,
    attr: FloatAttr | None,
    default: FloatAttr = 0.0,
) -> float | None:
    """Resolve a `FloatAttr` to a plain `float`, falling back to `default`
    (itself resolved the same way) when `attr` is `None`."""
    val = get_attr(ctx, attr, default)
    if isinstance(val, (int, float)):
        return val
    if val is None:
        return 0.0
    return float(val)


def get_attr(
    ctx: AnyContext | AnySharedContext,
    attr: Any,
    default: Any,
) -> Any | None:
    """Resolve the two shapes every typed `*Attr` getter is built on: `attr`
    may be a plain value or a callable taking `ctx` (which is what a `Tpl`
    is) — falling back to `default`, itself resolved the same way, when `attr`
    is `None`.

    A plain `str` is a literal. Rendering is opt-in: wrap it in `Tpl` to have
    it rendered against `ctx`.
    """
    if attr is None:
        if callable(default):
            return default(ctx)
        return default
    if callable(attr):
        return attr(ctx)
    return attr
