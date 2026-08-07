"""Tests for model-adaptive prompt profiles and presets (ADR-0047, ADR-0075)."""

import pytest

from zrb.llm.prompt.profile import (
    BASE_PROFILE,
    MICRO_PROFILE,
    MICRO_SECTIONS,
    MICRO_TOOLS,
    MINI_PROFILE,
    MINI_SECTIONS,
    ModelProfileRegistry,
    model_profile_registry,
    register_model_profile,
    resolve_preset,
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
    # A family name is still never read as a capability signal (ADR-0047):
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
    """`explicit` was renamed to `mini` with no alias (ADR-0047)."""
    # An unrecognized ZRB_LLM_PROFILE falls through to auto-resolution.
    assert resolve_profile("explicit", "anthropic:claude-opus-4") == BASE_PROFILE
    with pytest.raises(ValueError, match="Unknown profile"):
        register_model_profile("legacy-model", "explicit")


# ── Presets (ADR-0075) ──────────────────────────────────────────────────


def test_auto_selects_micro_only_from_a_declared_size_of_4b_or_less():
    for model in ["ollama:qwen2.5:3b", "ollama:llama3.2:3B", "local/phi-2b", "tiny-1b"]:
        assert resolve_profile("auto", model) == MICRO_PROFILE, model


def test_the_size_bands_do_not_overlap():
    """5B-14B stays on `mini`; `micro` must not swallow the band above it."""
    for model in ["mistral-7b", "gemma-2-9b", "qwen2.5-14b"]:
        assert resolve_profile("auto", model) == MINI_PROFILE, model
    for model in ["qwen2.5-32b", "llama-3-70b", "deepseek-405b"]:
        assert resolve_profile("auto", model) == BASE_PROFILE, model


def test_vendor_small_tier_labels_stay_on_mini():
    """`micro` removes capability, so a label is not enough to select it.

    `mini` only *adds* demonstrations, so a false positive is cheap. `micro`
    drops sections and tools, so a false positive is expensive — and `nano`
    /`tiny` label models (`gpt-5-nano`) far more capable than a 3B local one.
    """
    for model in [
        "openai:gpt-5-nano",
        "openai:gpt-5-mini",
        "anthropic:claude-haiku-4-5",
    ]:
        assert resolve_profile("auto", model) == MINI_PROFILE, model


def test_a_user_declaration_can_still_force_micro():
    register_model_profile("my-local-model", MICRO_PROFILE)
    assert resolve_profile("auto", "my-local-model") == MICRO_PROFILE


def test_terse_constrains_nothing():
    """`terse` is the unconstrained baseline every other preset subtracts from."""
    preset = resolve_preset(BASE_PROFILE)
    assert (preset.sections, preset.variant, preset.tools) == (None, None, None)


def test_only_micro_constrains_the_tool_axis():
    """`mini` keeps every capability; it lightens the rulebook, not the surface.

    A 5-14B model can still use skills, todos and delegation, so trimming its
    tools would cost behaviour rather than burden. Only `micro` goes that far.
    """
    assert resolve_preset(MINI_PROFILE).tools is None
    assert resolve_preset(MICRO_PROFILE).tools == MICRO_TOOLS


def test_mini_swaps_the_workflow_section_and_keeps_its_examples_variant():
    """`mini` lightens rules by *composition* and adds demonstrations by variant.

    Both axes at once, in opposite directions: fewer rules (a section swap,
    which is guarded and tested) plus more worked examples (a variant, which
    ADR-0047 permits). A variant may never subtract, which is why the lighter
    rulebook cannot be a `workflow.mini.md`.
    """
    preset = resolve_preset(MINI_PROFILE)
    assert preset.sections == MINI_SECTIONS
    assert "workflow_mini" in preset.sections
    assert "workflow" not in preset.sections
    assert preset.variant == MINI_PROFILE


def test_micro_binds_all_three_axes_and_carries_no_variant():
    """`micro` subtracts by composition, never by a variant overlay (ADR-0047)."""
    preset = resolve_preset(MICRO_PROFILE)
    assert preset.sections == MICRO_SECTIONS
    assert preset.tools == MICRO_TOOLS
    assert preset.variant is None


def test_an_unknown_profile_degrades_to_the_full_surface():
    """A stale config must lose nothing rather than land on a crippled preset."""
    preset = resolve_preset("no-such-profile")
    assert (preset.sections, preset.variant, preset.tools) == (None, None, None)
