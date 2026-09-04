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
        resolver.model_getter = "not-callable"


def test_model_renderer_setter_rejects_non_callable(resolver: ModelResolver):
    with pytest.raises(TypeError, match="model_renderer"):
        resolver.model_renderer = "not-callable"


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
    marker = object()
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
