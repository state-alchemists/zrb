from typing import Any
from unittest.mock import patch

import pytest

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import (
    ModelResolver,
    resolve_configured_model,
    resolve_configured_multimodal_model,
    resolve_configured_small_model,
)


@pytest.fixture
def resolver() -> ModelResolver:
    return ModelResolver()


# --- ModelResolver.resolve --------------------------------------------------


def test_resolve_non_string_model_passed_through(resolver: ModelResolver):
    marker: Any = object()
    assert resolver.resolve(marker) is marker


def test_resolve_none_passed_through(resolver: ModelResolver):
    assert resolver.resolve(None) is None


def test_resolve_native_provider_returned_as_is(resolver: ModelResolver):
    assert resolver.resolve("anthropic:claude-3-opus") == "anthropic:claude-3-opus"


def test_resolve_openai_without_credentials_returned_as_is(resolver: ModelResolver):
    assert resolver.resolve("openai:gpt-4o") == "openai:gpt-4o"


def test_resolve_unknown_provider_without_credentials_returned_as_is(
    resolver: ModelResolver,
):
    assert resolver.resolve("totally-unknown-provider:some-model") == (
        "totally-unknown-provider:some-model"
    )


def test_resolve_openai_with_api_key_resolves_to_model_object(resolver: ModelResolver):
    from pydantic_ai.models.openai import OpenAIChatModel

    resolved = resolver.resolve("openai:gpt-4o", api_key="secret")

    assert isinstance(resolved, OpenAIChatModel)


def test_resolve_unknown_provider_with_api_key_resolves_to_model_object(
    resolver: ModelResolver,
):
    from pydantic_ai.models.openai import OpenAIChatModel

    resolved = resolver.resolve("totally-unknown-provider:some-model", api_key="secret")

    assert isinstance(resolved, OpenAIChatModel)


def test_resolve_unknown_provider_with_explicit_string_provider(
    resolver: ModelResolver,
):
    resolved = resolver.resolve(
        "totally-unknown-provider:some-model",
        api_key="secret",
        provider="custom-provider",
    )

    assert resolved == "custom-provider:some-model"


def test_resolve_native_provider_with_api_key_receives_the_key(
    resolver: ModelResolver,
):
    """Regression: a `deepseek:`/`anthropic:`-prefixed model with LLM_API_KEY set
    used to come back as a bare string, so pydantic-ai built the provider from
    its own vendor env var and failed asking for DEEPSEEK_API_KEY -- a variable
    the user never set, having configured LLM_API_KEY instead."""
    resolved = resolver.resolve("deepseek:deepseek-chat", api_key="secret")

    from pydantic_ai.models import Model

    assert isinstance(resolved, Model)
    assert resolved.model_name == "deepseek-chat"


def test_resolve_native_provider_with_base_url_it_accepts(resolver: ModelResolver):
    """`AnthropicProvider` takes `base_url`, so both credentials go straight to
    the native provider and the model keeps its own class."""
    from pydantic_ai.models.anthropic import AnthropicModel

    resolved = resolver.resolve(
        "anthropic:claude-3-opus",
        api_key="secret",
        base_url="https://proxy.example/v1",
    )

    assert isinstance(resolved, AnthropicModel)
    assert resolved.model_name == "claude-3-opus"


def test_resolve_native_provider_with_base_url_it_rejects_falls_back_to_openai(
    resolver: ModelResolver,
):
    """`DeepSeekProvider` has no `base_url` parameter. Dropping the knob would
    silently ignore the endpoint the user asked for, so the OpenAI-compatible
    path takes over -- every provider reached this way speaks that wire format."""
    from pydantic_ai.models.openai import OpenAIChatModel

    resolved = resolver.resolve(
        "deepseek:deepseek-chat",
        api_key="secret",
        base_url="https://gateway.example/v1",
    )

    assert isinstance(resolved, OpenAIChatModel)
    assert resolved.model_name == "deepseek-chat"


def test_resolve_native_provider_without_credentials_still_returned_as_is(
    resolver: ModelResolver,
):
    """No configured credentials means the vendor's own env var is exactly what
    should be read -- the bare name is what hands pydantic-ai that job."""
    assert resolver.resolve("deepseek:deepseek-chat") == "deepseek:deepseek-chat"


def test_resolve_model_without_provider_prefix_defaults_to_openai(
    resolver: ModelResolver,
):
    resolved = resolver.resolve("gpt-4o", api_key="secret")

    from pydantic_ai.models.openai import OpenAIChatModel

    assert isinstance(resolved, OpenAIChatModel)


# --- resolve_configured_model -----------------------------------------------


def test_resolve_configured_model_uses_cfg_default(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MODEL", "anthropic:claude-3-opus")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)

    assert resolve_configured_model() == "anthropic:claude-3-opus"


def test_resolve_configured_model_explicit_override_wins(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MODEL", "anthropic:claude-3-opus")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)

    assert resolve_configured_model("openai:gpt-4o") == "openai:gpt-4o"


# --- resolve_configured_small_model -----------------------------------------


def test_resolve_configured_small_model_uses_cfg_small_model(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-4o")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "anthropic:claude-3-haiku")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)

    assert resolve_configured_small_model() == "anthropic:claude-3-haiku"


def test_resolve_configured_small_model_falls_back_to_main_model(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-4o")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", None)
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)

    assert resolve_configured_small_model() == "openai:gpt-4o"


def test_resolve_configured_small_model_prefers_current_run_model(monkeypatch):
    """A `/model deepseek:...` switch must carry the summarizer/journal with it:
    falling back to CFG.LLM_MODEL would demand the default provider's
    credentials on a run that never uses it."""
    from zrb.llm.agent_state import current_model

    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-4o")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", None)
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)
    token = current_model.set("deepseek:deepseek-chat")
    try:
        assert resolve_configured_small_model() == "deepseek:deepseek-chat"
    finally:
        current_model.reset(token)


def test_resolve_configured_small_model_cfg_small_model_beats_run_model(monkeypatch):
    """An explicitly configured small model still outranks the run's model."""
    from zrb.llm.agent_state import current_model

    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-4o")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "anthropic:claude-3-haiku")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)
    token = current_model.set("deepseek:deepseek-chat")
    try:
        assert resolve_configured_small_model() == "anthropic:claude-3-haiku"
    finally:
        current_model.reset(token)


def test_resolve_configured_small_model_explicit_override_wins(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-4o")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "anthropic:claude-3-haiku")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)

    assert resolve_configured_small_model("openai:gpt-4o-mini") == "openai:gpt-4o-mini"


# --- resolve_configured_multimodal_model ------------------------------------


def test_resolve_configured_multimodal_model_prefers_run_override(monkeypatch):
    """`/model multimodal <name>` outranks `CFG.LLM_MULTIMODAL_MODEL`."""
    from zrb.llm.agent_state import current_multimodal_model

    monkeypatch.setattr(CFG, "LLM_MULTIMODAL_MODEL", "openai:gpt-4o")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)
    token = current_multimodal_model.set("google-gla:gemini-2.5-flash")
    try:
        assert resolve_configured_multimodal_model() == "google-gla:gemini-2.5-flash"
    finally:
        current_multimodal_model.reset(token)


def test_resolve_configured_multimodal_model_never_falls_back_to_main_model(
    monkeypatch,
):
    """No multimodal model configured stays `None` — a text-only main model
    cannot read the attachment, which is why this tier exists at all."""
    from zrb.llm.agent_state import current_model

    monkeypatch.setattr(CFG, "LLM_MULTIMODAL_MODEL", "")
    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-4o")
    token = current_model.set("deepseek:deepseek-chat")
    try:
        assert resolve_configured_multimodal_model() is None
    finally:
        current_model.reset(token)


def test_resolve_configured_multimodal_model_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MULTIMODAL_MODEL", None)

    assert resolve_configured_multimodal_model() is None


def test_resolve_configured_multimodal_model_uses_cfg(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MULTIMODAL_MODEL", "openai:gpt-4o")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)

    assert resolve_configured_multimodal_model() == "openai:gpt-4o"


def test_resolve_configured_multimodal_model_explicit_override_wins(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MULTIMODAL_MODEL", "openai:gpt-4o")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)

    assert (
        resolve_configured_multimodal_model("anthropic:claude-3-opus")
        == "anthropic:claude-3-opus"
    )


def test_module_singleton_is_model_resolver_instance():
    from zrb.llm.config.model_resolver import model_resolver

    assert isinstance(model_resolver, ModelResolver)


# --- model_getter / model_renderer (global hooks) ---------------------------


def test_hooks_default_to_none(resolver: ModelResolver):
    assert resolver.model_getter is None
    assert resolver.model_renderer is None


def test_model_getter_setter_rejects_non_callable(resolver: ModelResolver):
    with pytest.raises(TypeError, match="model_getter"):
        resolver.model_getter = "not-callable"  # type: ignore[assignment]


def test_model_renderer_setter_rejects_non_callable(resolver: ModelResolver):
    with pytest.raises(TypeError, match="model_renderer"):
        resolver.model_renderer = "not-callable"  # type: ignore[assignment]


def test_model_getter_setter_accepts_none(resolver: ModelResolver):
    resolver.model_getter = lambda m: m
    resolver.model_getter = None
    assert resolver.model_getter is None


def test_resolve_applies_model_getter_then_model_renderer(resolver: ModelResolver):
    calls = []

    def getter(model):
        calls.append(("getter", model))
        return f"got:{model}"

    def renderer(model):
        calls.append(("renderer", model))
        return f"rendered:{model}"

    resolver.model_getter = getter
    resolver.model_renderer = renderer

    resolved = resolver.resolve("totally-unknown-provider:some-model")

    assert resolved == "rendered:got:totally-unknown-provider:some-model"
    assert calls == [
        ("getter", "totally-unknown-provider:some-model"),
        ("renderer", "got:totally-unknown-provider:some-model"),
    ]


def test_resolve_without_hooks_is_unaffected(resolver: ModelResolver):
    assert resolver.resolve("anthropic:claude-3-opus") == "anthropic:claude-3-opus"


def test_resolve_hooks_do_not_fire_for_non_string_model(resolver: ModelResolver):
    marker: Any = object()
    resolver.model_getter = lambda m: pytest.fail("model_getter must not run")
    resolver.model_renderer = lambda m: pytest.fail("model_renderer must not run")

    assert resolver.resolve(marker) is marker


def test_resolve_configured_model_applies_global_hooks(monkeypatch):
    from zrb.llm.config.model_resolver import model_resolver

    monkeypatch.setattr(CFG, "LLM_MODEL", "bsim:gemini-3.5-flash")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)
    monkeypatch.setattr(model_resolver, "_model_getter", None)
    monkeypatch.setattr(model_resolver, "_model_renderer", lambda m: f"proxy:{m}")

    assert resolve_configured_model() == "proxy:bsim:gemini-3.5-flash"


# ---------------------------------------------------------------------------
# Native-provider credential precedence
#
# `LLM_API_KEY` is provider-*agnostic*: it says nothing about which vendor it
# is a key for. A vendor variable is provider-*specific*, so it has to win,
# or a key set for `LLM_MODEL`'s provider gets force-fed to a differently
# prefixed `LLM_SMALL_MODEL` and 401s.
# ---------------------------------------------------------------------------


def test_vendor_env_var_beats_the_generic_api_key(resolver, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "vendor-anthropic-key")

    model = resolver.resolve("anthropic:claude-sonnet-4-5", api_key="generic-key")

    assert model.provider.client.api_key == "vendor-anthropic-key"


def test_generic_api_key_is_used_when_the_vendor_has_no_variable(resolver, monkeypatch):
    """The case the native branch exists for: an explicit `LLM_API_KEY` must
    not be silently dropped in favour of a vendor variable nobody set."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    model = resolver.resolve("deepseek:deepseek-chat", api_key="generic-key")

    assert model.provider.name == "deepseek"
    assert model.provider.client.api_key == "generic-key"


def test_explicit_base_url_overrides_the_vendor_default(resolver, monkeypatch):
    """A custom endpoint is a deliberate override, so it skips the vendor rung
    even when the vendor variable is set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "vendor-anthropic-key")

    model = resolver.resolve(
        "anthropic:claude-sonnet-4-5",
        api_key="generic-key",
        base_url="https://proxy/v1",
    )

    assert str(model.provider.base_url).startswith("https://proxy/v1")
    assert model.provider.client.api_key == "generic-key"


def test_base_url_a_native_provider_rejects_falls_back_to_openai_compatible(
    resolver, monkeypatch
):
    """`DeepSeekProvider` takes no `base_url`, and dropping it would silently
    ignore the whole reason the knob was set."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    model = resolver.resolve(
        "deepseek:deepseek-chat", api_key="generic-key", base_url="https://proxy/v1"
    )

    assert model.provider.name == "openai"
    assert str(model.provider.base_url).startswith("https://proxy/v1")


def test_explicit_provider_instance_for_the_same_vendor_is_honored(
    resolver, monkeypatch
):
    """A caller who hands over a configured `Provider` gets that object back,
    not a rebuild from `LLM_API_KEY` that quietly loses its `base_url`."""
    # lazy: heavy third-party
    from pydantic_ai.providers.anthropic import AnthropicProvider

    monkeypatch.setenv("ANTHROPIC_API_KEY", "vendor-anthropic-key")
    mine = AnthropicProvider(api_key="my-key", base_url="https://mine/v1")

    model = resolver.resolve(
        "anthropic:claude-sonnet-4-5", api_key="generic-key", provider=mine
    )

    assert model.provider is mine


def test_unbuildable_native_provider_falls_back_to_the_bare_name(resolver, monkeypatch):
    """`infer_provider_class` raising must not take the whole resolve with it.

    The bare name is the right fallback: pydantic-ai then raises its own
    "set `<VENDOR>_API_KEY`" message instead of this code inventing a worse
    one. The first resolve primes the resolver's native-provider cache so the
    patch below is seen only by `_resolve_native_model`, which is the call
    site under test.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert resolver.resolve("anthropic:claude-sonnet-4-5") == (
        "anthropic:claude-sonnet-4-5"
    )

    with patch(
        "pydantic_ai.providers.infer_provider_class",
        side_effect=ValueError("Unknown provider"),
    ):
        resolved = resolver.resolve("anthropic:claude-sonnet-4-5", api_key="generic")

    assert resolved == "anthropic:claude-sonnet-4-5"
