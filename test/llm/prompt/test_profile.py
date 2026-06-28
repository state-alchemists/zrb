"""Tests for model-adaptive prompt profiles (ADR-0083)."""

import pytest

from zrb.llm.prompt.profile import (
    BASE_PROFILE,
    EXPLICIT_PROFILE,
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


def test_explicit_and_terse_are_forced_regardless_of_model():
    assert resolve_profile("terse", "deepseek:deepseek-v4") == BASE_PROFILE
    assert resolve_profile("explicit", "anthropic:claude-opus-4") == EXPLICIT_PROFILE


def test_auto_defaults_to_terse_with_no_declarations():
    # zrb makes no capability guess from the id — strong, weak, and unknown
    # models all resolve to terse until a mapping is declared.
    for model in [
        "anthropic:claude-opus-4-8",
        "deepseek:deepseek-v4-pro",  # a frontier model — must NOT be guessed weak
        "ollama:qwen2.5-7b",
        "some-unrecognized-model",
        None,
    ]:
        assert resolve_profile("auto", model) == BASE_PROFILE, model


def test_none_or_blank_profile_behaves_like_auto():
    assert resolve_profile(None, "deepseek-v4") == BASE_PROFILE
    assert resolve_profile("", "claude-opus") == BASE_PROFILE


def test_unknown_profile_value_falls_through_to_auto():
    assert resolve_profile("bogus", "claude-opus") == BASE_PROFILE


def test_declared_mapping_drives_auto_resolution():
    register_model_profile("my-tiny-7b", "explicit")
    assert resolve_profile("auto", "ollama:my-tiny-7b") == EXPLICIT_PROFILE
    # A non-matching model is unaffected.
    assert resolve_profile("auto", "anthropic:claude-opus-4") == BASE_PROFILE


def test_declared_mapping_matches_model_object():
    register_model_profile(r"gemma-2-9b", "explicit")
    assert resolve_profile("auto", _Model("ollama:gemma-2-9b")) == EXPLICIT_PROFILE


def test_pattern_matches_full_id_without_stripping_any_segment():
    # The full id is matched as-is — provider, model, and tier all visible.
    cloud_model = "ollama:deepseek-v4-flash:cloud"
    # A model-name substring matches (and is NOT reduced to just "cloud").
    register_model_profile("deepseek-v4-flash", "explicit")
    assert resolve_profile("auto", cloud_model) == EXPLICIT_PROFILE


def test_pattern_can_match_provider_or_tier():
    register_model_profile(r"^ollama:", "explicit")
    assert resolve_profile("auto", "ollama:anything:cloud") == EXPLICIT_PROFILE
    assert resolve_profile("auto", "anthropic:claude-opus-4") == BASE_PROFILE


def test_most_recent_declaration_wins():
    register_model_profile("foo", "terse")
    register_model_profile("foo", "explicit")
    assert resolve_profile("auto", "foo-model") == EXPLICIT_PROFILE


def test_explicit_knob_overrides_a_terse_declaration():
    register_model_profile("foo", "terse")
    # The explicit knob is authoritative; declarations only feed auto.
    assert resolve_profile("explicit", "foo-model") == EXPLICIT_PROFILE


def test_set_rejects_invalid_profile():
    with pytest.raises(ValueError):
        model_profile_registry.set("foo", "verbose")


def test_isolated_registry_instance_does_not_touch_singleton():
    isolated = ModelProfileRegistry()
    isolated.set("foo", "explicit")
    assert isolated.resolve("foo-model") == EXPLICIT_PROFILE
    # Singleton remains empty.
    assert model_profile_registry.resolve("foo-model") is None
