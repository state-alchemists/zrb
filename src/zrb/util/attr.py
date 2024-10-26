from typing import Any
from collections.abc import Callable
from ..attr.type import AnyAttr, StrAttr, BoolAttr, IntAttr, FloatAttr
from ..context.any_shared_context import AnySharedContext


def get_str_attr(
    shared_ctx: AnySharedContext,
    attr: StrAttr | None,
    default: StrAttr,
    auto_render: bool = True
) -> str:
    return _get_attr(
        shared_ctx=shared_ctx,
        attr=attr,
        default=default,
        shared_ctx_renderer=shared_ctx.render,
        auto_render=auto_render
    )


def get_bool_attr(
    shared_ctx: AnySharedContext,
    attr: BoolAttr | None,
    default: BoolAttr,
    auto_render: bool = True
) -> str:
    return _get_attr(
        shared_ctx=shared_ctx,
        attr=attr,
        default=default,
        shared_ctx_renderer=shared_ctx.render_bool,
        auto_render=auto_render
    )


def get_int_attr(
    shared_ctx: AnySharedContext,
    attr: IntAttr | None,
    default: IntAttr,
    auto_render: bool = True
) -> str:
    return _get_attr(
        shared_ctx=shared_ctx,
        attr=attr,
        default=default,
        shared_ctx_renderer=shared_ctx.render_int,
        auto_render=auto_render
    )


def get_float_attr(
    shared_ctx: AnySharedContext,
    attr: FloatAttr | None,
    default: FloatAttr,
    auto_render: bool = True
) -> str:
    return _get_attr(
        shared_ctx=shared_ctx,
        attr=attr,
        default=default,
        shared_ctx_renderer=shared_ctx.render_float,
        auto_render=auto_render
    )


def _get_attr(
    shared_ctx: AnySharedContext,
    attr: AnyAttr,
    default: AnyAttr,
    shared_ctx_renderer: Callable[[str], Any],
    auto_render: bool = True,
) -> Any:
    if attr is None:
        if callable(default):
            return default(shared_ctx)
        return default
    if callable(attr):
        return attr(shared_ctx)
    if isinstance(attr, str) and auto_render:
        return shared_ctx_renderer(attr)
    return attr
