"""Resolve configured model names into pydantic-ai models."""

import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.agent_state import (
    get_current_model,
    get_current_multimodal_model,
    get_current_small_model,
)

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider

    ModelHook = Callable[["str | Model | None"], "str | Model | None"]


def require_model_hook(value: "ModelHook | None", label: str) -> "ModelHook | None":
    """Return *value* if it is a callable or None; raise `TypeError` naming
    *label* otherwise."""
    if value is not None and not callable(value):
        raise TypeError(
            f"{label} must be a callable or None, got {type(value).__name__}."
        )
    return value


def apply_model_hooks(
    model: "str | Model",
    model_getter: "ModelHook | None",
    model_renderer: "ModelHook | None",
) -> "str | Model | None":
    """Apply *model_getter* then *model_renderer* to *model*; either may return None."""
    active = model_getter(model) if model_getter else model
    return model_renderer(active) if model_renderer else active


class ModelResolver:
    """Resolve model names with optional provider credentials and hooks."""

    def __init__(self) -> None:
        self._native_provider_cache: dict[str, bool] = {}
        self._model_getter: "ModelHook | None" = None
        self._model_renderer: "ModelHook | None" = None

    @property
    def model_getter(
        self,
    ) -> "ModelHook | None":
        """Global getter applied before the renderer."""
        return self._model_getter

    @model_getter.setter
    def model_getter(self, value: "ModelHook | None") -> None:
        self._model_getter = require_model_hook(value, "model_resolver.model_getter")

    @property
    def model_renderer(
        self,
    ) -> "ModelHook | None":
        """Global renderer applied after the getter."""
        return self._model_renderer

    @model_renderer.setter
    def model_renderer(self, value: "ModelHook | None") -> None:
        self._model_renderer = require_model_hook(
            value, "model_resolver.model_renderer"
        )

    def resolve(
        self,
        model: "str | Model | None" = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        provider: "str | Provider | None" = None,
    ) -> "str | Model | None":
        """Resolve *model* into a `pydantic_ai` `Model` using the given
        credentials, then apply `model_getter`/`model_renderer` if set."""
        if not isinstance(model, str):
            return model
        resolved_provider = self._resolve_provider(provider, api_key, base_url, model)
        resolved = self._resolve_model_by_name(
            model, api_key, base_url, resolved_provider
        )
        return apply_model_hooks(resolved, self._model_getter, self._model_renderer)

    def _resolve_provider(
        self,
        provider: "str | Provider | None",
        api_key: str | None,
        base_url: str | None,
        model: "str | Model | None" = None,
    ) -> "str | Provider":
        if provider is not None:
            return provider
        # Credentials without a provider mean an OpenAI-compatible endpoint.
        if api_key or base_url:
            # lazy: heavy third-party
            from pydantic_ai.providers.openai import OpenAIProvider

            return OpenAIProvider(
                api_key=_openai_compatible_key(api_key, model), base_url=base_url
            )
        return "openai"

    def _resolve_model_by_name(
        self,
        model_name: str,
        api_key: str | None,
        base_url: str | None,
        provider: "str | Provider",
    ) -> "str | Model":
        provider_name = "openai"
        if ":" in model_name:
            provider_name = model_name.split(":", 1)[0]
        elif provider:
            # An explicit provider names the vendor of a bare model name as
            # surely as a `provider:` prefix does; otherwise
            # `LLM_PROVIDER=anthropic` + `LLM_MODEL=claude-x` would route as
            # OpenAI and drop LLM_API_KEY/LLM_BASE_URL.
            named = provider if isinstance(provider, str) else provider.name
            provider_name = named
            model_name = f"{named}:{model_name}"
        # A `Provider` instance is itself a fully configured credential.
        # `_resolve_provider` yields the plain string "openai" when nothing was
        # supplied, so this stays False in that case.
        has_credentials = bool(api_key or base_url) or not isinstance(provider, str)
        # Without credentials the bare name is right: pydantic-ai builds the
        # provider and reads that vendor's own env var.
        if not has_credentials:
            return model_name
        # "openai-chat" is pydantic-ai's prefix for the same backend as
        # "openai"; both go through OpenAIProvider so custom credentials apply.
        if provider_name not in (
            "openai",
            "openai-chat",
        ) and self._is_native_provider(provider_name):
            return self._resolve_native_model(
                model_name, provider_name, api_key, base_url, provider
            )
        # OpenAI itself, or an unknown provider behind an OpenAI-compatible
        # endpoint.
        return self._resolve_model(
            model_name,
            self._credentialed_provider(provider, api_key, base_url, model_name),
        )

    def _credentialed_provider(
        self,
        provider: "str | Provider",
        api_key: str | None,
        base_url: str | None,
        model_name: str,
    ) -> "str | Provider":
        """Return *provider*, or build an OpenAI-compatible provider from credentials."""
        if not isinstance(provider, str):
            return provider
        return self._resolve_provider(None, api_key, base_url, model_name)

    def _resolve_native_model(
        self,
        model_name: str,
        provider_name: str,
        api_key: str | None,
        base_url: str | None,
        provider: "str | Provider",
    ) -> "str | Model":
        """Build a native model with the supplied provider credentials."""
        # lazy: heavy third-party
        from pydantic_ai.models import infer_model
        from pydantic_ai.providers import infer_provider_class

        if not isinstance(provider, str) and provider.name == provider_name:
            return infer_model(model_name, provider_factory=lambda _: provider)
        try:
            provider_class = infer_provider_class(provider_name)
        except (ImportError, ValueError):
            return model_name
        accepted = inspect.signature(provider_class.__init__).parameters
        if base_url and "base_url" not in accepted:
            # `_resolve_provider(None, ...)` rather than the incoming
            # *provider*: that argument may be the plain `LLM_PROVIDER` string,
            # and `_resolve_model` turns a string provider back into a bare
            # `"<provider>:<model>"` name — dropping the endpoint this branch
            # exists to preserve.
            return self._resolve_model(
                model_name, self._resolve_provider(None, api_key, base_url, model_name)
            )
        kwargs: dict[str, str] = {}
        if api_key and "api_key" in accepted:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        if not kwargs:
            return model_name
        return infer_model(
            model_name, provider_factory=lambda _: provider_class(**kwargs)
        )

    def _is_native_provider(self, provider_name: str) -> bool:
        """Check if pydantic-ai has native support for a provider, with caching."""
        cache = self._native_provider_cache
        if provider_name not in cache:
            try:
                # lazy: heavy third-party
                from pydantic_ai.providers import infer_provider_class

                infer_provider_class(provider_name)
                cache[provider_name] = True
            except (ImportError, ValueError):
                cache[provider_name] = False
        return cache[provider_name]

    def _resolve_model(
        self, model_name: str, provider: "str | Provider"
    ) -> "str | Model":
        clean_model_name = model_name.split(":", 1)[-1]
        try:
            # lazy: heavy third-party
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider

            if isinstance(provider, OpenAIProvider):
                return OpenAIChatModel(model_name=clean_model_name, provider=provider)
        except ImportError:
            pass
        if isinstance(provider, str):
            return f"{provider}:{clean_model_name}"
        return model_name


#: The shared model resolver every zrb LLM call site uses. Stateless besides
#: its provider-support cache, so one instance is safe to share everywhere.
model_resolver = ModelResolver()


def _provider_prefix(model: "str | Model | None") -> str:
    """The provider a model name names, or `""` for a bare name."""
    if not isinstance(model, str) or ":" not in model:
        return ""
    return model.split(":", 1)[0]


def _openai_compatible_key(
    api_key: str | None, model: "str | Model | None"
) -> "str | None":
    """Return the compatible-provider key without leaking OpenAI credentials."""
    if api_key:
        return api_key
    if _provider_prefix(model) in ("", "openai", "openai-chat"):
        return None
    return "api-key-not-set"


def _configured_credentials(model: "str | Model | None") -> tuple[str, str]:
    """Read configured credentials, withholding mismatched vendor keys."""
    api_key, base_url = CFG.LLM_API_KEY, CFG.LLM_BASE_URL
    if base_url or not api_key:
        return api_key, base_url
    configured = CFG.LLM_PROVIDER or _provider_prefix(CFG.LLM_MODEL)
    target = _provider_prefix(model)
    if configured and target and configured != target:
        return "", ""
    return api_key, base_url


def resolve_configured_model(model: "str | Model | None" = None) -> "str | Model":
    """Resolve *model* (or `CFG.LLM_MODEL`) using the configured credentials."""
    resolved = _resolve_with_configured_credentials(model or CFG.LLM_MODEL)
    assert resolved is not None  # CFG.LLM_MODEL always has a non-empty default
    return resolved


def resolve_configured_small_model(model: "str | Model | None" = None) -> "str | Model":
    """Resolve the small model using run, small-model, then main-model settings."""
    target = (
        model
        or get_current_small_model()
        or CFG.LLM_SMALL_MODEL
        or get_current_model()
        or CFG.LLM_MODEL
    )
    resolved = _resolve_with_configured_credentials(target)
    assert resolved is not None  # CFG.LLM_MODEL always has a non-empty default
    return resolved


def resolve_configured_multimodal_model(
    model: "str | Model | None" = None,
) -> "str | Model | None":
    """Resolve the configured multimodal model, or return `None` if unset."""
    target = model or get_current_multimodal_model() or CFG.LLM_MULTIMODAL_MODEL
    if not target:
        return None
    return _resolve_with_configured_credentials(target)


def _resolve_with_configured_credentials(
    target: "str | Model",
) -> "str | Model | None":
    api_key, base_url = _configured_credentials(target)
    return model_resolver.resolve(
        target, api_key=api_key, base_url=base_url, provider=CFG.LLM_PROVIDER
    )
