'Credential and endpoint selection for model resolution.'

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





def test_resolve_native_provider_with_api_key_receives_the_key(
    resolver: ModelResolver,
):
    'A prefixed model uses the explicit generic API key.'
    resolved = resolver.resolve("deepseek:deepseek-chat", api_key="secret")

    from pydantic_ai.models import Model

    assert isinstance(resolved, Model)
    assert resolved.model_name == "deepseek-chat"


def test_resolve_native_provider_with_base_url_it_accepts(resolver: ModelResolver):
    '`AnthropicProvider` takes `base_url`, so both credentials go straight to'
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
    '`DeepSeekProvider` has no `base_url` parameter. Dropping the knob would'
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
    "No configured credentials means the vendor's own env var is exactly what"
    assert resolver.resolve("deepseek:deepseek-chat") == "deepseek:deepseek-chat"












def test_explicit_api_key_beats_an_ambient_vendor_variable(resolver, monkeypatch):
    'The resolver never second-guesses a credential it was handed. An'
    monkeypatch.setenv("ANTHROPIC_API_KEY", "vendor-anthropic-key")

    model = resolver.resolve("anthropic:claude-sonnet-4-5", api_key="generic-key")

    assert model.provider.client.api_key == "generic-key"


def test_no_api_key_leaves_the_vendor_variable_to_pydantic_ai(resolver, monkeypatch):
    'With nothing configured the bare name is right: pydantic-ai builds the'
    monkeypatch.setenv("ANTHROPIC_API_KEY", "vendor-anthropic-key")

    assert resolver.resolve("anthropic:claude-sonnet-4-5") == (
        "anthropic:claude-sonnet-4-5"
    )


def test_generic_api_key_is_used_when_the_vendor_has_no_variable(resolver, monkeypatch):
    'The case the native branch exists for: an explicit `LLM_API_KEY` must'
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    model = resolver.resolve("deepseek:deepseek-chat", api_key="generic-key")

    assert model.provider.name == "deepseek"
    assert model.provider.client.api_key == "generic-key"


def test_explicit_base_url_overrides_the_vendor_default(resolver, monkeypatch):
    'A custom endpoint is a deliberate override, so it skips the vendor rung'
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
    '`DeepSeekProvider` takes no `base_url`, and dropping it would silently'
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    model = resolver.resolve(
        "deepseek:deepseek-chat", api_key="generic-key", base_url="https://proxy/v1"
    )

    assert model.provider.name == "openai"
    assert str(model.provider.base_url).startswith("https://proxy/v1")


def test_explicit_provider_instance_for_the_same_vendor_is_honored(
    resolver, monkeypatch
):
    'A caller who hands over a configured `Provider` gets that object back,'
    # lazy: heavy third-party
    from pydantic_ai.providers.anthropic import AnthropicProvider

    monkeypatch.setenv("ANTHROPIC_API_KEY", "vendor-anthropic-key")
    mine = AnthropicProvider(api_key="my-key", base_url="https://mine/v1")

    model = resolver.resolve(
        "anthropic:claude-sonnet-4-5", api_key="generic-key", provider=mine
    )

    assert model.provider is mine


def test_unbuildable_native_provider_falls_back_to_the_bare_name(resolver, monkeypatch):
    '`infer_provider_class` raising must not take the whole resolve with it.'
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resolver.resolve("anthropic:claude-sonnet-4-5", api_key="generic")

    with patch(
        "pydantic_ai.providers.infer_provider_class",
        side_effect=ValueError("Unknown provider"),
    ):
        resolved = resolver.resolve("anthropic:claude-sonnet-4-5", api_key="generic")

    assert resolved == "anthropic:claude-sonnet-4-5"











def test_generic_key_reaches_a_model_of_its_own_provider(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ambient-vendor-key")
    monkeypatch.setattr(CFG, "LLM_MODEL", "deepseek:deepseek-chat")
    monkeypatch.setattr(CFG, "LLM_API_KEY", "configured-key")
    monkeypatch.setattr(CFG, "LLM_BASE_URL", "")
    monkeypatch.setattr(CFG, "LLM_PROVIDER", "")

    model = resolve_configured_model()

    assert model.provider.client.api_key == "configured-key"


def test_generic_key_is_withheld_from_a_differently_prefixed_model(monkeypatch):
    '`LLM_SMALL_MODEL=anthropic:…` beside `LLM_MODEL=openai:…` is the shape'
    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-5")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "anthropic:claude-haiku-4-5")
    monkeypatch.setattr(CFG, "LLM_API_KEY", "an-openai-key")
    monkeypatch.setattr(CFG, "LLM_BASE_URL", "")
    monkeypatch.setattr(CFG, "LLM_PROVIDER", "")

    assert resolve_configured_small_model() == "anthropic:claude-haiku-4-5"


def test_llm_provider_names_the_vendor_the_key_belongs_to(monkeypatch):
    "An explicit `LLM_PROVIDER` outranks `LLM_MODEL`'s prefix as the answer"
    monkeypatch.setattr(CFG, "LLM_MODEL", "some-bare-name")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "anthropic:claude-haiku-4-5")
    monkeypatch.setattr(CFG, "LLM_API_KEY", "a-groq-key")
    monkeypatch.setattr(CFG, "LLM_BASE_URL", "")
    monkeypatch.setattr(CFG, "LLM_PROVIDER", "groq")

    assert resolve_configured_small_model() == "anthropic:claude-haiku-4-5"


def test_a_base_url_makes_the_key_travel_to_every_tier(monkeypatch):
    'One endpoint for every model is the gateway case (LiteLLM, OpenRouter).'
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







def test_openai_key_is_not_inherited_by_a_foreign_vendor_over_a_custom_url(
    resolver, monkeypatch
):
    '`DeepSeekProvider` takes no `base_url`, so a gateway URL sends a'
    monkeypatch.setenv("OPENAI_API_KEY", "sk-my-real-openai-secret")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    model = resolver.resolve("deepseek:deepseek-chat", base_url="https://gw.example/v1")

    assert model.provider.client.api_key != "sk-my-real-openai-secret"
    assert model.provider.client.api_key == "api-key-not-set"


def test_openai_key_is_still_inherited_when_the_target_is_openai(resolver, monkeypatch):
    'The other half of the rule: an openai-prefixed model over a custom'
    monkeypatch.setenv("OPENAI_API_KEY", "sk-my-real-openai-secret")

    model = resolver.resolve("openai:gpt-5", base_url="https://gw.example/v1")

    assert model.provider.client.api_key == "sk-my-real-openai-secret"


def test_a_bare_model_name_over_a_custom_url_still_inherits_openai_key(
    resolver, monkeypatch
):
    'No prefix means the OpenAI backend by definition (ADR-0037), so the'
    monkeypatch.setenv("OPENAI_API_KEY", "sk-my-real-openai-secret")

    model = resolver.resolve("some-local-model", base_url="https://gw.example/v1")

    assert model.provider.client.api_key == "sk-my-real-openai-secret"













def test_bare_model_with_provider_openai_keeps_its_api_key(resolver):
    from pydantic_ai.models.openai import OpenAIChatModel

    model = resolver.resolve("gpt-5", api_key="zrb-key", provider="openai")

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "gpt-5"
    assert model.provider.client.api_key == "zrb-key"


def test_bare_model_with_provider_openai_keeps_its_base_url(resolver):
    model = resolver.resolve(
        "gpt-5", api_key="zrb-key", base_url="https://gw/v1", provider="openai"
    )

    assert model.provider.client.api_key == "zrb-key"
    assert str(model.provider.base_url).startswith("https://gw/v1")


def test_bare_model_with_provider_anthropic_routes_to_anthropic(resolver):
    'Routing first: attaching credentials without fixing the route would'
    from pydantic_ai.models.anthropic import AnthropicModel

    model = resolver.resolve("claude-x", api_key="zrb-key", provider="anthropic")

    assert isinstance(model, AnthropicModel)
    assert model.model_name == "claude-x"
    assert model.provider.name == "anthropic"
    assert model.provider.client.api_key == "zrb-key"


def test_bare_model_with_provider_anthropic_keeps_its_base_url(resolver):
    model = resolver.resolve(
        "claude-x", api_key="zrb-key", base_url="https://gw/v1", provider="anthropic"
    )

    assert model.provider.client.api_key == "zrb-key"
    assert str(model.provider.base_url).startswith("https://gw/v1")


def test_bare_model_with_a_provider_instance_routes_by_its_name(resolver):
    'A `Provider` instance answers "which vendor" through `.name`, and had'
    # lazy: heavy third-party
    from pydantic_ai.providers.anthropic import AnthropicProvider

    mine = AnthropicProvider(api_key="my-key", base_url="https://mine/v1")

    model = resolver.resolve("claude-x", provider=mine)

    assert model.provider is mine
    assert model.model_name == "claude-x"


def test_bare_model_with_provider_string_and_no_credentials_is_unchanged(resolver):
    'Nothing to attach, so the prefixed name still goes to pydantic-ai --'
    assert resolver.resolve("claude-x", provider="anthropic") == "anthropic:claude-x"


def test_configured_provider_and_bare_model_carry_credentials_end_to_end(monkeypatch):
    'The whole reported shape, through the knobs a user actually sets.'
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(CFG, "LLM_MODEL", "claude-sonnet-4-5")
    monkeypatch.setattr(CFG, "LLM_API_KEY", "my-anthropic-key")
    monkeypatch.setattr(CFG, "LLM_BASE_URL", "https://my-gateway/v1")

    model = resolve_configured_model()

    assert model.provider.client.api_key == "my-anthropic-key"
    assert str(model.provider.base_url).startswith("https://my-gateway/v1")


def test_configured_provider_still_scopes_the_key_for_a_foreign_small_model(
    monkeypatch,
):
    'Routing by `LLM_PROVIDER` must not undo the withholding rule: the key'
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(CFG, "LLM_MODEL", "claude-sonnet-4-5")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "deepseek:deepseek-chat")
    monkeypatch.setattr(CFG, "LLM_API_KEY", "my-anthropic-key")
    monkeypatch.setattr(CFG, "LLM_BASE_URL", "")

    assert resolve_configured_small_model() == "deepseek:deepseek-chat"
