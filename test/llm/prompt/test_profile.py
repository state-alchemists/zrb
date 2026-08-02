"""Tests for model-adaptive prompt profiles (ADR-0083)."""

import pytest

from zrb.llm.prompt.profile import (
    BASE_PROFILE,
    MINI_PROFILE,
    ModelProfileRegistry,
    model_profile_registry,
    register_model_profile,
    resolve_profile,
)


class _Model:
    def __init__(self, model_name):
        self.model_name = model_name


@pytest.fixture(autouse=True)
def _clean_registry():
    """Each test starts with no declared model→profile mappings."""
    model_profile_registry.clear()
    yield
    model_profile_registry.clear()


def test_mini_and_terse_are_forced_regardless_of_model():
    assert resolve_profile("terse", "deepseek:deepseek-v4") == BASE_PROFILE
    assert resolve_profile("mini", "anthropic:claude-opus-4") == MINI_PROFILE


def test_auto_stays_terse_for_models_that_declare_no_small_size():
    # A family name is still never read as a capability signal (ADR-0093):
    # only a stated size token or a vendor small-tier label selects explicit.
    for model in [
        "anthropic:claude-opus-4-8",
        "deepseek:deepseek-v4-pro",  # a frontier model — must NOT be guessed weak
        "some-unrecognized-model",
        None,
    ]:
        assert resolve_profile("auto", model) == BASE_PROFILE, model


def test_auto_selects_mini_from_a_declared_small_size():
    """A parameter count in the id is the vendor stating the size, not a guess."""
    for model in [
        "ollama:qwen2.5-7b",
        "ollama:gemma-2-9b",
        "qwen3-14b",
        "openai:gpt-5-mini",
        "anthropic:claude-haiku-4-5",
    ]:
        assert resolve_profile("auto", model) == MINI_PROFILE, model


def test_auto_does_not_read_a_large_declared_size_as_small():
    """The size rule accepts 1-14B only; bigger stated counts stay terse."""
    for model in ["qwen3-32b", "llama-3-70b", "llama-3.1-405b"]:
        assert resolve_profile("auto", model) == BASE_PROFILE, model


def test_flash_is_a_latency_tier_not_a_size_and_stays_terse():
    """`flash` spans weak to strong, so it is opt-in rather than a default."""
    assert resolve_profile("auto", "gemini-2.5-flash") == BASE_PROFILE
    assert resolve_profile("auto", "deepseek:deepseek-v4-flash") == BASE_PROFILE
    register_model_profile("deepseek-v4-flash", "mini")
    assert resolve_profile("auto", "deepseek:deepseek-v4-flash") == MINI_PROFILE


def test_a_user_declaration_overrides_a_built_in_default():
    register_model_profile("qwen2.5-7b", "terse")
    assert resolve_profile("auto", "ollama:qwen2.5-7b") == BASE_PROFILE


def test_built_in_defaults_survive_clearing_user_declarations():
    model_profile_registry.clear()
    assert resolve_profile("auto", "ollama:qwen2.5-7b") == MINI_PROFILE


def test_a_registry_without_defaults_matches_nothing():
    from zrb.llm.prompt.profile import ModelProfileRegistry

    isolated = ModelProfileRegistry(defaults=())
    assert isolated.resolve("ollama:qwen2.5-7b") is None
    isolated.set("qwen2.5-7b", "mini")
    assert isolated.resolve("ollama:qwen2.5-7b") == MINI_PROFILE


def test_none_or_blank_profile_behaves_like_auto():
    assert resolve_profile(None, "deepseek-v4") == BASE_PROFILE
    assert resolve_profile("", "claude-opus") == BASE_PROFILE


def test_unknown_profile_value_falls_through_to_auto():
    assert resolve_profile("bogus", "claude-opus") == BASE_PROFILE


def test_declared_mapping_drives_auto_resolution():
    register_model_profile("my-tiny-7b", "mini")
    assert resolve_profile("auto", "ollama:my-tiny-7b") == MINI_PROFILE
    # A non-matching model is unaffected.
    assert resolve_profile("auto", "anthropic:claude-opus-4") == BASE_PROFILE


def test_declared_mapping_matches_model_object():
    register_model_profile(r"gemma-2-9b", "mini")
    assert resolve_profile("auto", _Model("ollama:gemma-2-9b")) == MINI_PROFILE


def test_pattern_matches_full_id_without_stripping_any_segment():
    # The full id is matched as-is — provider, model, and tier all visible.
    cloud_model = "ollama:deepseek-v4-flash:cloud"
    # A model-name substring matches (and is NOT reduced to just "cloud").
    register_model_profile("deepseek-v4-flash", "mini")
    assert resolve_profile("auto", cloud_model) == MINI_PROFILE


def test_pattern_can_match_provider_or_tier():
    register_model_profile(r"^ollama:", "mini")
    assert resolve_profile("auto", "ollama:anything:cloud") == MINI_PROFILE
    assert resolve_profile("auto", "anthropic:claude-opus-4") == BASE_PROFILE


def test_most_recent_declaration_wins():
    register_model_profile("foo", "terse")
    register_model_profile("foo", "mini")
    assert resolve_profile("auto", "foo-model") == MINI_PROFILE


def test_mini_knob_overrides_a_terse_declaration():
    register_model_profile("foo", "terse")
    # The explicit knob is authoritative; declarations only feed auto.
    assert resolve_profile("mini", "foo-model") == MINI_PROFILE


def test_set_rejects_invalid_profile():
    with pytest.raises(ValueError):
        model_profile_registry.set("foo", "verbose")


def test_isolated_registry_instance_does_not_touch_singleton():
    isolated = ModelProfileRegistry()
    isolated.set("foo", "mini")
    assert isolated.resolve("foo-model") == MINI_PROFILE
    # Singleton remains empty.
    assert model_profile_registry.resolve("foo-model") is None


def test_the_old_explicit_value_is_no_longer_a_profile():
    """`explicit` was renamed to `mini` with no alias (ADR-0095)."""
    # An unrecognized ZRB_LLM_PROFILE falls through to auto-resolution.
    assert resolve_profile("explicit", "anthropic:claude-opus-4") == BASE_PROFILE
    with pytest.raises(ValueError, match="Unknown profile"):
        register_model_profile("legacy-model", "explicit")
