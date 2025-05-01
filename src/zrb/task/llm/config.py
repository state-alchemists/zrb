from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
else:
    Model = Any
    ModelSettings = Any

from zrb.attr.type import StrAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.llm_config import LLMConfig
from zrb.llm_config import llm_config as default_llm_config
from zrb.util.attr import get_attr


def get_model_settings(
    ctx: AnyContext,
    model_settings_attr: (
        ModelSettings | Callable[[AnySharedContext], ModelSettings] | None
    ),
) -> ModelSettings | None:
    """Gets the model settings, resolving callables if necessary."""
    if callable(model_settings_attr):
        return model_settings_attr(ctx)
    return model_settings_attr


def get_model_base_url(
    ctx: AnyContext,
    model_base_url_attr: StrAttr | None,
    render_model_base_url: bool,
) -> str | None:
    """Gets the model base URL, rendering if configured."""
    base_url = get_attr(
        ctx, model_base_url_attr, None, auto_render=render_model_base_url
    )
    if isinstance(base_url, str) or base_url is None:
        return base_url
    raise ValueError(f"Invalid model base URL: {base_url}")


def get_model_api_key(
    ctx: AnyContext,
    model_api_key_attr: StrAttr | None,
    render_model_api_key: bool,
) -> str | None:
    """Gets the model API key, rendering if configured."""
    api_key = get_attr(ctx, model_api_key_attr, None, auto_render=render_model_api_key)
    if isinstance(api_key, str) or api_key is None:
        return api_key
    raise ValueError(f"Invalid model API key: {api_key}")


def get_model(
    ctx: AnyContext,
    model_attr: Callable[[AnySharedContext], Model | str | fstring] | Model | None,
    render_model: bool,
    model_base_url_attr: StrAttr | None,
    render_model_base_url: bool,
    model_api_key_attr: StrAttr | None,
    render_model_api_key: bool,
) -> str | Model | None:
    """Gets the model instance or name, handling defaults and configuration."""
    from pydantic_ai.models import Model

    model = get_attr(ctx, model_attr, None, auto_render=render_model)
    if model is None:
        return default_llm_config.get_default_model()
    if isinstance(model, str):
        model_base_url = get_model_base_url(
            ctx, model_base_url_attr, render_model_base_url
        )
        model_api_key = get_model_api_key(ctx, model_api_key_attr, render_model_api_key)
        llm_config = LLMConfig(
            default_model_name=model,
            default_base_url=model_base_url,
            default_api_key=model_api_key,
        )
        if model_base_url is None and model_api_key is None:
            default_model_provider = default_llm_config.get_default_model_provider()
            if default_model_provider is not None:
                llm_config.set_default_provider(default_model_provider)
        return llm_config.get_default_model()
    # If it's already a Model instance, return it directly
    if isinstance(model, Model):
        return model
    raise ValueError(f"Invalid model type resolved: {type(model)}, value: {model}")
