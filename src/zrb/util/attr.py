from typing import Any

from zrb.attr.type import (
    AnyAttr,
    BoolAttr,
    FloatAttr,
    IntAttr,
    StrAttr,
    StrDictAttr,
    StrListAttr,
)
from zrb.context.any_shared_context import AnySharedContext
from zrb.util.string.conversion import to_boolean


def get_str_list_attr(
    shared_ctx: AnySharedContext, attr: StrListAttr | None, auto_render: bool = True
) -> list[str]:
    if callable(attr):
        return attr(shared_ctx)
    return {get_str_attr(shared_ctx, val, "", auto_render) for val in attr}


def get_str_dict_attr(
    shared_ctx: AnySharedContext, attr: StrDictAttr | None, auto_render: bool = True
) -> dict[str, Any]:
    if callable(attr):
        return attr(shared_ctx)
    return {
        key: get_str_attr(shared_ctx, val, "", auto_render) for key, val in attr.items()
    }


def get_str_attr(
    shared_ctx: AnySharedContext,
    attr: StrAttr | None,
    default: StrAttr = "",
    auto_render: bool = True,
) -> str:
    val = get_attr(shared_ctx, attr, default, auto_render)
    if not isinstance(val, str):
        return str(val)
    return val


def get_bool_attr(
    shared_ctx: AnySharedContext,
    attr: BoolAttr | None,
    default: BoolAttr = False,
    auto_render: bool = True,
) -> bool:
    val = get_attr(shared_ctx, attr, default, auto_render)
    if isinstance(val, str):
        return to_boolean(val)
    return val


def get_int_attr(
    shared_ctx: AnySharedContext,
    attr: IntAttr | None,
    default: IntAttr = 0,
    auto_render: bool = True,
) -> int:
    val = get_attr(shared_ctx, attr, default, auto_render)
    if isinstance(val, str):
        return int(val)
    return val


def get_float_attr(
    shared_ctx: AnySharedContext,
    attr: FloatAttr | None,
    default: FloatAttr = 0.0,
    auto_render: bool = True,
) -> str | None:
    val = get_attr(shared_ctx, attr, default, auto_render)
    if isinstance(val, str):
        return float(val)
    return val


def get_attr(
    shared_ctx: AnySharedContext,
    attr: AnyAttr,
    default: AnyAttr,
    auto_render: bool = True,
) -> Any | None:
    if attr is None:
        if callable(default):
            return default(shared_ctx)
        return default
    if callable(attr):
        return attr(shared_ctx)
    if isinstance(attr, str) and auto_render:
        return shared_ctx.render(attr)
    return attr
