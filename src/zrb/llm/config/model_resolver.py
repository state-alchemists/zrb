"""Pure model-name resolution — job 2 of the old `LLMConfig` (R12,
`framework-conventions.md`).

Job 1 (the override-layer-over-`CFG` half) is gone: every scalar `LLMConfig`
used to hold (`model`, `small_model`, `multimodal_model`, `api_key`,
`base_url`, `provider`) is a `CFG.LLM_*` knob now, and the two callable hooks
(`model_getter`, `model_renderer`) are settable slots directly on `LLMTask`/
`LLMChatTask` — see `docs/changelog/v3/3.0.0.md` for the migration table.

This module is what's left: turning a `"provider:name"` string plus
credentials into a `pydantic_ai` `Model` object. It has nothing to do with
configuration, so it does not become part of `CFG`.

`ModelResolver` also holds its own `model_getter`/`model_renderer` pair — a
*global* fallback for the same two hooks, applied by every
`resolve_configured_*` function. A task's own `model_getter`/`model_renderer`
only reaches that one task; this reaches every call site that resolves
through `CFG.LLM_MODEL` et al., including sub-agent delegation
(`SubAgentBuilding.resolve_agent_build`), which has no task of its own to
hold a per-task hook. Set once in `zrb_init.py` for a process-wide default —
see `docs/changelog/v3/3.0.0.md` for why the old `llm_config.model_getter`/
`model_renderer` (process-wide by accident, on a config object) became this
(process-wide on purpose, on the resolver whose job it actually extends).
"""

from typing import TYPE_CHECKING, Callable

from zrb.config.config import CFG

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.providers import Provider

    ModelHook = Callable[["str | Model | None"], "str | Model | None"]


class ModelResolver:
    """Turns a model name plus credentials into a pydantic-ai `Model`.

    Pure resolution plus two optional global hooks: it reads nothing and
    stores nothing besides a small provider-support cache
    (`_is_native_provider`'s memoization — the pydantic-ai provider registry
    it queries doesn't change at runtime, so caching costs nothing real) and
    the `model_getter`/`model_renderer` pair below. Give it a name and the
    credentials to use; it returns a `Model` (or the name unchanged when the
    provider is a plain string, or `model` itself unchanged when it isn't a
    string at all — an already-resolved `Model` object, or `None`).
    """

    def __init__(self) -> None:
        self._native_provider_cache: dict[str, bool] = {}
        self._model_getter: "ModelHook | None" = None
        self._model_renderer: "ModelHook | None" = None

    @property
    def model_getter(
        self,
    ) -> "ModelHook | None":
        """Global default `model_getter`, applied to every `resolve_configured_*`
        result before `model_renderer`. See the module docstring for scope."""
        return self._model_getter

    @model_getter.setter
    def model_getter(self, value: "ModelHook | None") -> None:
        if value is not None and not callable(value):
            raise TypeError(
                "model_resolver.model_getter must be a callable or None, "
                f"got {type(value).__name__}"
            )
        self._model_getter = value

    @property
    def model_renderer(
        self,
    ) -> "ModelHook | None":
        """Global default `model_renderer`, applied to every `resolve_configured_*`
        result after `model_getter`. See the module docstring for scope."""
        return self._model_renderer

    @model_renderer.setter
    def model_renderer(self, value: "ModelHook | None") -> None:
        if value is not None and not callable(value):
            raise TypeError(
                "model_resolver.model_renderer must be a callable or None, "
                f"got {type(value).__name__}"
            )
        self._model_renderer = value

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
        resolved_provider = self._resolve_provider(provider, api_key, base_url)
        resolved = self._resolve_model_by_name(
            model, api_key, base_url, resolved_provider
        )
        return self._apply_hooks(resolved)

    def _apply_hooks(self, model: "str | Model") -> "str | Model | None":
        active = self._model_getter(model) if self._model_getter else model
        return self._model_renderer(active) if self._model_renderer else active

    def _resolve_provider(
        self,
        provider: "str | Provider | None",
        api_key: str | None,
        base_url: str | None,
    ) -> "str | Provider":
        if provider is not None:
            return provider
        # If API Key or Base URL is set, we assume OpenAI-compatible provider
        if api_key or base_url:
            # lazy: heavy third-party
            from pydantic_ai.providers.openai import OpenAIProvider

            return OpenAIProvider(api_key=api_key, base_url=base_url)
        return "openai"

    def _resolve_model_by_name(
        self,
        model_name: str,
        api_key: str | None,
        base_url: str | None,
        provider: "str | Provider",
    ) -> "str | Model":
        provider_name, has_prefix = "openai", False
        if ":" in model_name:
            provider_name, has_prefix = model_name.split(":", 1)[0], True
        # Special case: the OpenAI backend goes through resolve logic when API
        # config is set (OpenAIProvider handles both OpenAI and OpenAI-compatible
        # APIs). "openai-chat" — pydantic-ai's model-prefix form, mirrored by the
        # shipped default ("openai:gpt-5.6-luna") with its plain "openai" prefix
        # — is the same backend, so neither must slip past this branch and
        # silently ignore a custom LLM_API_KEY/LLM_BASE_URL.
        if provider_name in ("openai", "openai-chat"):
            # An explicit `LLM_PROVIDER` on a bare model name (no provider prefix)
            # with no API key/base URL to pin an OpenAIProvider: honor it, so
            # `ZRB_LLM_PROVIDER=anthropic` + `ZRB_LLM_MODEL=claude-x` isn't
            # silently dropped. An explicit `openai:`/`openai-chat:` prefix, or
            # API credentials present, takes the normal OpenAI path below.
            if (
                isinstance(provider, str)
                and provider
                and not has_prefix
                and not (api_key or base_url)
            ):
                return f"{provider}:{model_name}"
            if api_key or base_url:
                return self._resolve_model(model_name, provider)
            return model_name
        # If provider is natively supported by pydantic-ai, return as-is
        # (pydantic-ai will use its built-in provider, reading env vars like
        #  OLLAMA_BASE_URL, ANTHROPIC_API_KEY, etc.)
        if self._is_native_provider(provider_name):
            return model_name
        # Unknown provider without pydantic-ai support
        # Use OpenAIProvider if API config is set (for OpenAI-compatible endpoints)
        if api_key or base_url:
            return self._resolve_model(model_name, provider)
        return model_name

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
        # Strip existing provider prefix if present
        clean_model_name = model_name.split(":", 1)[-1]
        # 1. Provider is an Object (e.g. OpenAIProvider created from custom config)
        # We check specific types we know how to wrap
        try:
            # lazy: heavy third-party
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider

            if isinstance(provider, OpenAIProvider):
                return OpenAIChatModel(model_name=clean_model_name, provider=provider)
        except ImportError:
            pass
        # 2. Provider is a String
        if isinstance(provider, str):
            return f"{provider}:{clean_model_name}"
        # 3. Fallback (Provider is None or unknown object)
        return model_name


#: The shared model resolver every zrb LLM call site uses. Stateless besides
#: its provider-support cache, so one instance is safe to share everywhere.
model_resolver = ModelResolver()


def resolve_configured_model(model: "str | Model | None" = None) -> "str | Model":
    """Resolve *model* (or `CFG.LLM_MODEL`) using the configured credentials."""
    resolved = model_resolver.resolve(
        model or CFG.LLM_MODEL,
        api_key=CFG.LLM_API_KEY,
        base_url=CFG.LLM_BASE_URL,
        provider=CFG.LLM_PROVIDER,
    )
    assert resolved is not None  # CFG.LLM_MODEL always has a non-empty default
    return resolved


def resolve_configured_small_model(model: "str | Model | None" = None) -> "str | Model":
    """Resolve *model* (or `CFG.LLM_SMALL_MODEL`, or the main model) using the
    configured credentials."""
    resolved = model_resolver.resolve(
        model or CFG.LLM_SMALL_MODEL or CFG.LLM_MODEL,
        api_key=CFG.LLM_API_KEY,
        base_url=CFG.LLM_BASE_URL,
        provider=CFG.LLM_PROVIDER,
    )
    assert resolved is not None  # CFG.LLM_MODEL always has a non-empty default
    return resolved


def resolve_configured_multimodal_model(
    model: "str | Model | None" = None,
) -> "str | Model | None":
    """Resolve *model* (or `CFG.LLM_MULTIMODAL_MODEL`) using the configured
    credentials, or `None` when no multimodal model is configured — callers
    fall back to dropping the attachment with a warning rather than silently
    sending binary content a text-only model cannot interpret."""
    resolved = model or CFG.LLM_MULTIMODAL_MODEL
    if not resolved:
        return None
    return model_resolver.resolve(
        resolved,
        api_key=CFG.LLM_API_KEY,
        base_url=CFG.LLM_BASE_URL,
        provider=CFG.LLM_PROVIDER,
    )
