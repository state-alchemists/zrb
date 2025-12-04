from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings

from zrb.attr.type import BoolAttr, StrAttr, StrListAttr
from zrb.config.llm_config import LLMConfig, llm_config
from zrb.context.any_context import AnyContext
from zrb.util.attr import get_attr, get_bool_attr, get_str_list_attr


def get_yolo_mode(
    ctx: AnyContext,
    yolo_mode_attr: (
        Callable[[AnyContext], list[str] | bool | None] | StrListAttr | BoolAttr | None
    ) = None,
    render_yolo_mode: bool = True,
) -> bool | list[str]:
    if yolo_mode_attr is None:
        return llm_config.default_yolo_mode
    try:
        return get_bool_attr(
            ctx,
            yolo_mode_attr,
            False,
            auto_render=render_yolo_mode,
        )
    except Exception:
        return get_str_list_attr(
            ctx,
            yolo_mode_attr,
            auto_render=render_yolo_mode,
        )


def get_model_settings(
    ctx: AnyContext,
    model_settings_attr: (
        "ModelSettings | Callable[[AnyContext], ModelSettings] | None"
    ) = None,
) -> "ModelSettings | None":
    """Gets the model settings, resolving callables if necessary."""
    model_settings = get_attr(ctx, model_settings_attr, None, auto_render=False)
    if model_settings is None:
        return llm_config.default_model_settings
    return model_settings


def get_model_base_url(
    ctx: AnyContext,
    model_base_url_attr: StrAttr | None = None,
    render_model_base_url: bool = True,
) -> str | None:
    """Gets the model base URL, rendering if configured."""
    base_url = get_attr(
        ctx, model_base_url_attr, None, auto_render=render_model_base_url
    )
    if base_url is None and llm_config.default_model_base_url is not None:
        return llm_config.default_model_base_url
    if isinstance(base_url, str) or base_url is None:
        return base_url
    raise ValueError(f"Invalid model base URL: {base_url}")


def get_model_api_key(
    ctx: AnyContext,
    model_api_key_attr: StrAttr | None = None,
    render_model_api_key: bool = True,
) -> str | None:
    """Gets the model API key, rendering if configured."""
    api_key = get_attr(ctx, model_api_key_attr, None, auto_render=render_model_api_key)
    if api_key is None and llm_config.default_model_api_key is not None:
        return llm_config.default_model_api_key
    if isinstance(api_key, str) or api_key is None:
        return api_key
    raise ValueError(f"Invalid model API key: {api_key}")


def get_model(
    ctx: AnyContext,
    model_attr: "Callable[[AnyContext], Model | str | None] | Model | str | None",
    render_model: bool,
    model_base_url_attr: "Callable[[AnyContext], Model | str | None] | Model | str | None",
    render_model_base_url: bool = True,
    model_api_key_attr: "Callable[[AnyContext], Model | str | None] | Model | str | None" = None,
    render_model_api_key: bool = True,
    is_small_model: bool = False,
) -> "str | Model":
    """Gets the model instance or name, handling defaults and configuration."""
    from pydantic_ai.models import Model

    model = get_attr(ctx, model_attr, None, auto_render=render_model)
    if model is None:
        if is_small_model:
            return llm_config.default_small_model
        return llm_config.default_model
    if isinstance(model, str):
        model_base_url = get_model_base_url(
            ctx, model_base_url_attr, render_model_base_url
        )
        model_api_key = get_model_api_key(ctx, model_api_key_attr, render_model_api_key)
        new_llm_config = LLMConfig(
            default_model_name=model,
            default_model_base_url=model_base_url,
            default_model_api_key=model_api_key,
        )
        if model_base_url is None and model_api_key is None:
            default_model_provider = _get_default_model_provider(is_small_model)
            if default_model_provider is not None:
                new_llm_config.set_default_model_provider(default_model_provider)
        return new_llm_config.default_model
    # If it's already a Model instance, return it directly
    if isinstance(model, Model):
        return model
    raise ValueError(f"Invalid model type resolved: {type(model)}, value: {model}")


def _get_default_model_provider(is_small_model: bool = False):
    if is_small_model:
        return llm_config.default_small_model_provider
    return llm_config.default_model_provider
