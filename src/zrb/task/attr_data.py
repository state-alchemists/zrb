from typing import Callable
from ..session.context import Context

StrAttr = str | Callable[[Context], str]
BoolAttr = bool | str | Callable[[Context], bool]
IntAttr = int | str | Callable[[Context], int]
FloatAttr = float | str | Callable[[Context], float]


def get_str_attr(
    ctx: Context,
    attr: StrAttr | None,
    default: StrAttr,
    auto_render: bool = True
) -> str:
    if attr is None:
        if callable(default):
            return default(ctx)
        return default
    if callable(attr):
        return attr(ctx)
    if isinstance(attr, str) and auto_render:
        return ctx.render(attr)
    if isinstance(attr, str):
        return attr
    return None


def get_bool_attr(
    ctx: Context,
    attr: BoolAttr | None,
    default: BoolAttr,
    auto_render: bool = True
) -> bool:
    if attr is None:
        if callable(default):
            return default(ctx)
        return default
    if callable(attr):
        return attr(ctx)
    if isinstance(attr, str) and auto_render:
        return ctx.render_bool(attr)
    if isinstance(attr, bool):
        return attr
    return None


def get_int_attr(
    ctx: Context,
    attr: IntAttr | None,
    default: IntAttr,
    auto_render: bool = True
) -> int:
    if attr is None:
        if callable(default):
            return default(ctx)
        return default
    if callable(attr):
        return attr(ctx)
    if isinstance(attr, str) and auto_render:
        return ctx.render_int(attr)
    if isinstance(attr, int):
        return attr
    return None


def get_float_attr(
    ctx: Context,
    attr: FloatAttr | None,
    default: FloatAttr,
    auto_render: bool = True
) -> float:
    if attr is None:
        if callable(default):
            return default(ctx)
        if isinstance(default, bool):
            return default
    if callable(attr):
        return attr(ctx)
    if isinstance(attr, str) and auto_render:
        return ctx.render_float(attr)
    if isinstance(attr, float):
        return attr
    return None
