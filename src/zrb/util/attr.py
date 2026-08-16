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
    auto_render: bool = True,
) -> list[str]:
    """Resolve a `StrListAttr` — `None`, a list of renderable strings, or a
    callable taking `ctx` — to a plain `list[str]`."""
    if attr is None:
        return []
    if callable(attr):
        return attr(ctx)
    return [get_str_attr(ctx, val, "", auto_render) for val in attr]


def get_str_dict_attr(
    ctx: AnyContext | AnySharedContext,
    attr: StrDictAttr | None,
    auto_render: bool = True,
) -> dict[str, Any]:
    """Resolve a `StrDictAttr` — `None`, a dict of renderable strings, or a
    callable taking `ctx` — to a plain `dict[str, Any]`."""
    if attr is None:
        return {}
    if callable(attr):
        return attr(ctx)
    return {key: get_str_attr(ctx, val, "", auto_render) for key, val in attr.items()}


def get_str_attr(
    ctx: AnyContext | AnySharedContext,
    attr: StrAttr | None,
    default: StrAttr = "",
    auto_render: bool = True,
) -> str:
    """Resolve a `StrAttr` to a plain `str`, falling back to `default` (itself
    resolved the same way) when `attr` is `None`."""
    val = get_attr(ctx, attr, default, auto_render)
    if isinstance(val, str):
        return val
    if val is None:
        return ""
    return str(val)


def get_bool_attr(
    ctx: AnyContext | AnySharedContext,
    attr: BoolAttr | None,
    default: BoolAttr = False,
    auto_render: bool = True,
) -> bool:
    """Resolve a `BoolAttr` to a plain `bool`, falling back to `default`
    (itself resolved the same way) when `attr` is `None`."""
    val = get_attr(ctx, attr, default, auto_render)
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return to_boolean(val)


def get_int_attr(
    ctx: AnyContext | AnySharedContext,
    attr: IntAttr | None,
    default: IntAttr = 0,
    auto_render: bool = True,
) -> int:
    """Resolve an `IntAttr` to a plain `int`, falling back to `default`
    (itself resolved the same way) when `attr` is `None`."""
    val = get_attr(ctx, attr, default, auto_render)
    if isinstance(val, int):
        return val
    if val is None:
        return 0
    return int(val)


def get_float_attr(
    ctx: AnyContext | AnySharedContext,
    attr: FloatAttr | None,
    default: FloatAttr = 0.0,
    auto_render: bool = True,
) -> float | None:
    """Resolve a `FloatAttr` to a plain `float`, falling back to `default`
    (itself resolved the same way) when `attr` is `None`."""
    val = get_attr(ctx, attr, default, auto_render)
    if isinstance(val, (int, float)):
        return val
    if val is None:
        return 0.0
    return float(val)


def get_attr(
    ctx: AnyContext | AnySharedContext,
    attr: Any,
    default: Any,
    auto_render: bool = True,
) -> Any | None:
    """Resolve the three shapes every typed `*Attr` getter is built on: `attr`
    may be a plain value, a callable taking `ctx`, or (when `auto_render`) a
    template string to render — falls back to `default`, itself resolved the
    same way, when `attr` is `None`."""
    if attr is None:
        if callable(default):
            return default(ctx)
        return default
    if callable(attr):
        return attr(ctx)
    if isinstance(attr, str) and auto_render:
        return ctx.render(attr)
    return attr
