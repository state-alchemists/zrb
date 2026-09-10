"""Credential resolution: which key and endpoint reach which provider.

Split from `test_model_resolver.py` by feature group — that file covers what
`resolve()` and the `resolve_configured_*` chain select as the *model*; this
one covers what they select as the *credentials*, which is the part ADR-0094
governs.
"""

from unittest.mock import patch

import pytest

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import (
    ModelResolver,
    resolve_configured_model,
    resolve_configured_small_model,
)


@pytest.fixture
def resolver() -> ModelResolver:
    return ModelResolver()


# --- Native providers -------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Native-provider credentials
#
# `ModelResolver` is deliberately literal: credentials handed to `resolve()`
# are credentials it uses, so explicit config beats an ambient vendor
# variable. Which vendor `LLM_API_KEY` was meant for is decided one layer up,
# in `resolve_configured_*` -- see the precedence tests further down.
# ---------------------------------------------------------------------------


def test_explicit_api_key_beats_an_ambient_vendor_variable(resolver, monkeypatch):
    """The resolver never second-guesses a credential it was handed. An
    ambient `ANTHROPIC_API_KEY` the user may not know is exported must not
    silently displace the key they configured -- that fails as a 401 with no
    way to override short of unsetting the variable."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "vendor-anthropic-key")

    model = resolver.resolve("anthropic:claude-sonnet-4-5", api_key="generic-key")

    assert model.provider.client.api_key == "generic-key"


def test_no_api_key_leaves_the_vendor_variable_to_pydantic_ai(resolver, monkeypatch):
    """With nothing configured the bare name is right: pydantic-ai builds the
    provider and reads the vendor variable itself."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "vendor-anthropic-key")

    assert resolver.resolve("anthropic:claude-sonnet-4-5") == (
        "anthropic:claude-sonnet-4-5"
    )


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


# ---------------------------------------------------------------------------
# Which vendor `LLM_API_KEY` belongs to
#
# The knob reads as provider-agnostic but never is: it is a key for the one
# provider the user configured, named by `LLM_PROVIDER` or by `LLM_MODEL`'s
# prefix. `resolve_configured_*` withholds it from any other vendor.
# ---------------------------------------------------------------------------


def test_generic_key_reaches_a_model_of_its_own_provider(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ambient-vendor-key")
    monkeypatch.setattr(CFG, "LLM_MODEL", "deepseek:deepseek-chat")
    monkeypatch.setattr(CFG, "LLM_API_KEY", "configured-key")
    monkeypatch.setattr(CFG, "LLM_BASE_URL", "")
    monkeypatch.setattr(CFG, "LLM_PROVIDER", "")

    model = resolve_configured_model()

    assert model.provider.client.api_key == "configured-key"


def test_generic_key_is_withheld_from_a_differently_prefixed_model(monkeypatch):
    """`LLM_SMALL_MODEL=anthropic:…` beside `LLM_MODEL=openai:…` is the shape
    that 401-ed on every summarization: the OpenAI key was force-fed to
    Anthropic. The bare name hands the job to `ANTHROPIC_API_KEY` instead."""
    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-5")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "anthropic:claude-haiku-4-5")
    monkeypatch.setattr(CFG, "LLM_API_KEY", "an-openai-key")
    monkeypatch.setattr(CFG, "LLM_BASE_URL", "")
    monkeypatch.setattr(CFG, "LLM_PROVIDER", "")

    assert resolve_configured_small_model() == "anthropic:claude-haiku-4-5"


def test_llm_provider_names_the_vendor_the_key_belongs_to(monkeypatch):
    """An explicit `LLM_PROVIDER` outranks `LLM_MODEL`'s prefix as the answer
    to "whose key is this", since it is the more direct statement of it."""
    monkeypatch.setattr(CFG, "LLM_MODEL", "some-bare-name")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "anthropic:claude-haiku-4-5")
    monkeypatch.setattr(CFG, "LLM_API_KEY", "a-groq-key")
    monkeypatch.setattr(CFG, "LLM_BASE_URL", "")
    monkeypatch.setattr(CFG, "LLM_PROVIDER", "groq")

    assert resolve_configured_small_model() == "anthropic:claude-haiku-4-5"


def test_a_base_url_makes_the_key_travel_to_every_tier(monkeypatch):
    """One endpoint for every model is the gateway case (LiteLLM, OpenRouter).
    Setting `LLM_BASE_URL` says exactly that, so the vendor test is off and
    the key follows the endpoint regardless of prefix."""
    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-5")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "anthropic:claude-haiku-4-5")
    monkeypatch.setattr(CFG, "LLM_API_KEY", "gateway-key")
    monkeypatch.setattr(CFG, "LLM_BASE_URL", "https://gateway/v1")
    monkeypatch.setattr(CFG, "LLM_PROVIDER", "")

    model = resolve_configured_small_model()

    assert model.provider.client.api_key == "gateway-key"
    assert str(model.provider.base_url).startswith("https://gateway/v1")


def test_a_bare_model_name_never_triggers_the_vendor_test(monkeypatch):
    """No prefix, no vendor to mismatch -- the key goes through, which is what
    keeps `LLM_MODEL=gpt-5` + `LLM_API_KEY=…` working."""
    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-5")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "gpt-5-mini")
    monkeypatch.setattr(CFG, "LLM_API_KEY", "an-openai-key")
    monkeypatch.setattr(CFG, "LLM_BASE_URL", "")
    monkeypatch.setattr(CFG, "LLM_PROVIDER", "")

    model = resolve_configured_small_model()

    assert model.provider.client.api_key == "an-openai-key"


# ---------------------------------------------------------------------------
# Whose key the OpenAI-compatible fallback may inherit
# ---------------------------------------------------------------------------


def test_openai_key_is_not_inherited_by_a_foreign_vendor_over_a_custom_url(
    resolver, monkeypatch
):
    """`DeepSeekProvider` takes no `base_url`, so a gateway URL sends a
    `deepseek:` model down the OpenAI-compatible path. Passing `api_key=None`
    there lets the OpenAI SDK read `OPENAI_API_KEY` itself -- attaching the
    user's OpenAI secret, as a bearer token, to requests aimed at whatever
    host `LLM_BASE_URL` names, for a vendor that key is not for."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-my-real-openai-secret")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    model = resolver.resolve("deepseek:deepseek-chat", base_url="https://gw.example/v1")

    assert model.provider.client.api_key != "sk-my-real-openai-secret"
    assert model.provider.client.api_key == "api-key-not-set"


def test_openai_key_is_still_inherited_when_the_target_is_openai(resolver, monkeypatch):
    """The other half of the rule: an openai-prefixed model over a custom
    endpoint is exactly the setup `OPENAI_API_KEY` is for, so nothing here may
    get in its way."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-my-real-openai-secret")

    model = resolver.resolve("openai:gpt-5", base_url="https://gw.example/v1")

    assert model.provider.client.api_key == "sk-my-real-openai-secret"


def test_a_bare_model_name_over_a_custom_url_still_inherits_openai_key(
    resolver, monkeypatch
):
    """No prefix means the OpenAI backend by definition (ADR-0037), so the
    common `LLM_BASE_URL` + bare-name + `OPENAI_API_KEY` setup is untouched."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-my-real-openai-secret")

    model = resolver.resolve("some-local-model", base_url="https://gw.example/v1")

    assert model.provider.client.api_key == "sk-my-real-openai-secret"
