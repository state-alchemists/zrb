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
    """
    Retrieve a list of strings from shared context attributes.

    Args:
        shared_ctx (AnySharedContext): The shared context object.
        attr (StrListAttr | None): The string list attribute to retrieve.
        auto_render (bool): Whether to auto-render the attribute values.

    Returns:
        list[str]: A list of string attributes.
    """
    if callable(attr):
        return attr(shared_ctx)
    return {get_str_attr(shared_ctx, val, "", auto_render) for val in attr}


def get_str_dict_attr(
    shared_ctx: AnySharedContext, attr: StrDictAttr | None, auto_render: bool = True
) -> dict[str, Any]:
    """
    Retrieve a dictionary of strings from shared context attributes.

    Args:
        shared_ctx (AnySharedContext): The shared context object.
        attr (StrDictAttr | None): The string dictionary attribute to retrieve.
        auto_render (bool): Whether to auto-render the attribute values.

    Returns:
        dict[str, Any]: A dictionary of string attributes.
    """
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
    """
    Retrieve a string from shared context attributes.

    Args:
        shared_ctx (AnySharedContext): The shared context object.
        attr (StrAttr | None): The string attribute to retrieve.
        default (StrAttr): The default value if the attribute is None.
        auto_render (bool): Whether to auto-render the attribute value.

    Returns:
        str: The string attribute value.
    """
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
    """
    Retrieve a boolean from shared context attributes.

    Args:
        shared_ctx (AnySharedContext): The shared context object.
        attr (BoolAttr | None): The boolean attribute to retrieve.
        default (BoolAttr): The default value if the attribute is None.
        auto_render (bool): Whether to auto-render the attribute value if it's a string.

    Returns:
        bool: The boolean attribute value.
    """
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
    """
    Retrieve an integer from shared context attributes.

    Args:
        shared_ctx (AnySharedContext): The shared context object.
        attr (IntAttr | None): The integer attribute to retrieve.
        default (IntAttr): The default value if the attribute is None.
        auto_render (bool): Whether to auto-render the attribute value if it's a string.

    Returns:
        int: The integer attribute value.
    """
    val = get_attr(shared_ctx, attr, default, auto_render)
    if isinstance(val, str):
        return int(val)
    return val


def get_float_attr(
    shared_ctx: AnySharedContext,
    attr: FloatAttr | None,
    default: FloatAttr = 0.0,
    auto_render: bool = True,
) -> float | None:
    """
    Retrieve a float from shared context attributes.

    Args:
        shared_ctx (AnySharedContext): The shared context object.
        attr (FloatAttr | None): The float attribute to retrieve.
        default (FloatAttr): The default value if the attribute is None.
        auto_render (bool): Whether to auto-render the attribute value if it's a string.

    Returns:
        float | None: The float attribute value.
    """
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
    """
    Retrieve an attribute value from shared context, handling callables and rendering.

    Args:
        shared_ctx (AnySharedContext): The shared context object.
        attr (AnyAttr): The attribute to retrieve. Can be a value, a callable,
            or a string to render.
        default (AnyAttr): The default value if the attribute is None.
        auto_render (bool): Whether to auto-render the attribute value if it's a string.

    Returns:
        Any | None: The retrieved attribute value or the default value.
    """
    if attr is None:
        if callable(default):
            return default(shared_ctx)
        return default
    if callable(attr):
        return attr(shared_ctx)
    if isinstance(attr, str) and auto_render:
        return shared_ctx.render(attr)
    return attr
