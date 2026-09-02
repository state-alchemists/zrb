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
    marker = object()
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


def test_resolve_configured_small_model_explicit_override_wins(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MODEL", "openai:gpt-4o")
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "anthropic:claude-3-haiku")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)

    assert resolve_configured_small_model("openai:gpt-4o-mini") == "openai:gpt-4o-mini"


# --- resolve_configured_multimodal_model ------------------------------------


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
