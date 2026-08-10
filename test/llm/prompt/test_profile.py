"""Tests for the explicit prompt-profile adjustment."""

import pytest

from zrb.llm.prompt.profile import (
    CAPABLE_PROFILE,
    MINIMAL_PROFILE,
    PROFILES,
    STANDARD_PROFILE,
    active_profile,
    builtin_profile,
    resolve_profile,
)


@pytest.mark.parametrize("profile", PROFILES)
def test_each_supported_profile_resolves_to_itself(profile):
    assert resolve_profile(profile) == profile


def test_unknown_or_missing_profile_falls_back_to_standard():
    assert resolve_profile(None) == STANDARD_PROFILE
    assert resolve_profile("unknown") == STANDARD_PROFILE


def test_profiles_are_the_three_documented_adjustments():
    assert PROFILES == (MINIMAL_PROFILE, STANDARD_PROFILE, CAPABLE_PROFILE)


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("ollama:phi4:3b", MINIMAL_PROFILE),
        ("deepseek-r1:1.5b", MINIMAL_PROFILE),
        ("qwen2.5-7b", STANDARD_PROFILE),
        ("qwen3-30b-a3b", CAPABLE_PROFILE),
        ("gpt-5", STANDARD_PROFILE),
    ],
)
def test_auto_resolves_declared_size_bands(model_id, expected):
    assert resolve_profile("auto", model_id) == expected


def test_auto_reads_the_first_declared_count():
    assert builtin_profile("qwen3-30b-a3b") == CAPABLE_PROFILE


def test_auto_uses_the_profile_default_when_the_id_declares_nothing():
    assert resolve_profile("auto", "gpt-5") == STANDARD_PROFILE
    assert resolve_profile("auto", None) == STANDARD_PROFILE


def test_small_tier_label_is_not_enough_on_its_own():
    assert builtin_profile("openai:gpt-5-nano") == STANDARD_PROFILE


def test_small_tier_label_plus_local_provider_selects_minimal():
    assert builtin_profile("ollama:phi4-mini") == MINIMAL_PROFILE
    # Ollama's hosted tier is not local: the label alone stays on `standard`.
    assert builtin_profile("ollama:phi4-mini:cloud") == STANDARD_PROFILE


def test_explicit_profile_outranks_the_model():
    assert resolve_profile("minimal", "qwen3-30b-a3b") == MINIMAL_PROFILE
    assert resolve_profile("capable", "ollama:phi4:3b") == CAPABLE_PROFILE


def test_active_profile_reads_the_knob(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_PROFILE", "capable")
    assert active_profile() == CAPABLE_PROFILE
    monkeypatch.setenv("ZRB_LLM_PROFILE", "auto")
    assert active_profile("qwen3-30b-a3b") == CAPABLE_PROFILE
