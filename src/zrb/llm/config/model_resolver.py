"""Pure model-name resolution (R12, `framework-conventions.md`).

Turns a `"provider:name"` string plus credentials into a `pydantic_ai`
`Model`. Resolution only — it holds no configuration and is not part of
`CFG`. The scalars it reads (`model`, `small_model`, `multimodal_model`,
`api_key`, `base_url`, `provider`) are `CFG.LLM_*` knobs, and the two callable
hooks (`model_getter`, `model_renderer`) are settable slots on `LLMTask` /
`LLMChatTask`. `docs/changelog/v3/3.0.0.md` has the migration table for
projects still passing an `LLMConfig`.

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

import inspect
from typing import TYPE_CHECKING, Callable

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
        resolved_provider = self._resolve_provider(provider, api_key, base_url, model)
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
        model: "str | Model | None" = None,
    ) -> "str | Provider":
        if provider is not None:
            return provider
        # If API Key or Base URL is set, we assume OpenAI-compatible provider
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
        # If provider is natively supported by pydantic-ai, let it build that
        # provider — but the credentials still have to reach it. A native
        # provider constructed with no arguments reads only its own vendor env
        # var (DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, OLLAMA_BASE_URL, ...), so
        # returning the bare name here would silently drop an explicit
        # LLM_API_KEY/LLM_BASE_URL and then fail asking for a vendor variable
        # the user never set. With no credentials configured, the bare name is
        # still right: that vendor env var is exactly what should be read.
        if self._is_native_provider(provider_name):
            if api_key or base_url:
                return self._resolve_native_model(
                    model_name, provider_name, api_key, base_url, provider
                )
            return model_name
        # Unknown provider without pydantic-ai support
        # Use OpenAIProvider if API config is set (for OpenAI-compatible endpoints)
        if api_key or base_url:
            return self._resolve_model(model_name, provider)
        return model_name

    def _resolve_native_model(
        self,
        model_name: str,
        provider_name: str,
        api_key: str | None,
        base_url: str | None,
        provider: "str | Provider",
    ) -> "str | Model":
        """Build a natively-supported model, choosing whose credentials to use.

        `infer_model`'s `provider_factory` seam is what makes the choice
        possible: pydantic-ai still picks the `Model` subclass the prefix maps
        to, but the provider it wraps is built here.

        Credentials only reach here when they belong to this vendor —
        `_configured_credentials` withholds a mismatched `LLM_API_KEY` at the
        config layer — so nothing below second-guesses them.

        Precedence, highest first:

        1. a `Provider` **instance** the caller handed in *for this same
           vendor* — fully configured already. The instance auto-built from
           `LLM_API_KEY` upstream is an `OpenAIProvider`, whose `.name` never
           matches a native non-openai prefix, so it correctly does not
           qualify;
        2. `api_key`/`base_url`, passed as whichever keyword arguments the
           constructor actually declares (`AnthropicProvider` takes
           `base_url`, `DeepSeekProvider` does not).

        With neither available the bare name is returned unchanged, so
        pydantic-ai builds the provider itself and reads that vendor's own
        variable — which is the only credential that could be right when zrb
        was given none. A `base_url` the native provider cannot accept falls
        through to the OpenAI-compatible path instead of being dropped: a
        custom endpoint is the whole reason to set that knob, and every
        provider zrb reaches this way speaks the OpenAI wire format.
        """
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
        # Strip existing provider prefix if present
        clean_model_name = model_name.split(":", 1)[-1]
        # Provider is an Object (e.g. OpenAIProvider created from custom config)
        # We check specific types we know how to wrap
        try:
            # lazy: heavy third-party
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider

            if isinstance(provider, OpenAIProvider):
                return OpenAIChatModel(model_name=clean_model_name, provider=provider)
        except ImportError:
            pass
        # Provider is a String
        if isinstance(provider, str):
            return f"{provider}:{clean_model_name}"
        # Fallback (Provider is None or unknown object)
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
    """The key to hand an OpenAI-*compatible* provider.

    Passing `None` is not "no key": `OpenAIProvider` forwards it to the OpenAI
    SDK, which reads `OPENAI_API_KEY` out of the environment. That is right
    when the target really is OpenAI — an unprefixed name means exactly that —
    and wrong the moment it is not. A `deepseek:`-prefixed model whose
    `LLM_BASE_URL` sends it down this compatibility path would otherwise
    attach the user's OpenAI secret, as a bearer token, to requests aimed at
    an unrelated host, for a vendor that key does not belong to.

    The placeholder returned instead is pydantic-ai's own, and is what it
    already substitutes when no key exists anywhere — so a keyless local
    gateway keeps working, and a real endpoint rejects the request loudly
    rather than quietly receiving the wrong credential.
    """
    if api_key:
        return api_key
    if _provider_prefix(model) in ("", "openai", "openai-chat"):
        return None
    return "api-key-not-set"


def _configured_credentials(model: "str | Model | None") -> tuple[str, str]:
    """`(api_key, base_url)` from `CFG`, with `LLM_API_KEY` withheld when it
    was configured for a different vendor than *model*'s.

    `LLM_API_KEY` reads as provider-agnostic but never is: a user sets it for
    the one provider they configured, named by `LLM_PROVIDER` or by
    `LLM_MODEL`'s own prefix. Handing it to a differently prefixed model — the
    shape `LLM_SMALL_MODEL=anthropic:…` beside `LLM_MODEL=openai:…` asks for —
    401s on every summarization. Withholding it lets the bare name through, and
    pydantic-ai then reads that vendor's own variable, which is the only
    credential that could be right there.

    Deciding it here rather than inside `ModelResolver` keeps the resolver
    honest: credentials handed to `resolve()` are credentials it uses, so
    explicit config always beats an ambient vendor variable. Only this layer
    knows *which* vendor `LLM_API_KEY` was meant for, because only this layer
    reads `LLM_MODEL`.

    An explicit `LLM_BASE_URL` disables the whole test. Pointing zrb at one
    endpoint is a statement that this endpoint serves every tier — the
    LiteLLM/OpenRouter-style gateway case — so its key travels with it.
    """
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
    target = model or CFG.LLM_MODEL
    api_key, base_url = _configured_credentials(target)
    resolved = model_resolver.resolve(
        target, api_key=api_key, base_url=base_url, provider=CFG.LLM_PROVIDER
    )
    assert resolved is not None  # CFG.LLM_MODEL always has a non-empty default
    return resolved


def resolve_configured_small_model(model: "str | Model | None" = None) -> "str | Model":
    """Resolve *model* (or `CFG.LLM_SMALL_MODEL`, or the main model) using the
    configured credentials.

    Precedence, highest first:

    1. the explicit *model* argument,
    2. `get_current_small_model()` — this run's `/model small <name>`,
    3. `CFG.LLM_SMALL_MODEL`,
    4. `get_current_model()` — the model this run is actually using, i.e. a
       `/model <name>` switch or `--model`,
    5. `CFG.LLM_MODEL`.

    The chain lives here rather than at each call site, which is what the
    summarizer got wrong: it called this with no argument, so `/model small`
    never reached the one consumer users most expect it to reach. A live slash
    command outranks static config (2 before 3) for the same reason `/model`
    outranks `CFG.LLM_MODEL`, and the run's own model outranks
    `CFG.LLM_MODEL` (4 before 5) because the configured default may well be a
    different provider whose credentials the user never set.
    """
    target = (
        model
        or get_current_small_model()
        or CFG.LLM_SMALL_MODEL
        or get_current_model()
        or CFG.LLM_MODEL
    )
    api_key, base_url = _configured_credentials(target)
    resolved = model_resolver.resolve(
        target, api_key=api_key, base_url=base_url, provider=CFG.LLM_PROVIDER
    )
    assert resolved is not None  # CFG.LLM_MODEL always has a non-empty default
    return resolved


def resolve_configured_multimodal_model(
    model: "str | Model | None" = None,
) -> "str | Model | None":
    """Resolve *model* (or `CFG.LLM_MULTIMODAL_MODEL`) using the configured
    credentials, or `None` when no multimodal model is configured — callers
    fall back to dropping the attachment with a warning rather than silently
    sending binary content a text-only model cannot interpret.

    Precedence, highest first: the explicit *model* argument,
    `get_current_multimodal_model()` (this run's `/model multimodal <name>`),
    then `CFG.LLM_MULTIMODAL_MODEL`. There is no fall back to the main model:
    a text-only model cannot read the attachment, which is the whole reason
    this tier exists."""
    resolved = model or get_current_multimodal_model() or CFG.LLM_MULTIMODAL_MODEL
    if not resolved:
        return None
    api_key, base_url = _configured_credentials(resolved)
    return model_resolver.resolve(
        resolved, api_key=api_key, base_url=base_url, provider=CFG.LLM_PROVIDER
    )
