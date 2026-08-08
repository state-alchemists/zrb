"""Tests for model-adaptive prompt profiles and presets (ADR-0047, ADR-0075)."""

import pytest

from zrb.llm.prompt.profile import (
    FULL_PROFILE,
    LEAN_PROFILE,
    MINIMAL_PROFILE,
    MINIMAL_SECTIONS,
    MINIMAL_TOOLS,
    PRESETS,
    ModelProfileRegistry,
    Preset,
    model_profile_registry,
    register_model_profile,
    resolve_preset,
    resolve_profile,
    valid_profiles,
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


def test_lean_and_full_are_forced_regardless_of_model():
    assert resolve_profile("full", "deepseek:deepseek-v4") == FULL_PROFILE
    assert resolve_profile("lean", "anthropic:claude-opus-4") == LEAN_PROFILE


def test_auto_stays_full_for_models_that_declare_no_small_size():
    # A family name is still never read as a capability signal (ADR-0047):
    # only a stated size token or a vendor small-tier label selects explicit.
    for model in [
        "anthropic:claude-opus-4-8",
        "deepseek:deepseek-v4-pro",  # a frontier model — must NOT be guessed weak
        "some-unrecognized-model",
        None,
    ]:
        assert resolve_profile("auto", model) == FULL_PROFILE, model


def test_auto_selects_lean_from_a_declared_small_size():
    """A parameter count in the id is the vendor stating the size, not a guess."""
    for model in [
        "ollama:qwen2.5-7b",
        "ollama:gemma-2-9b",
        "qwen3-14b",
        "openai:gpt-5-mini",
        "anthropic:claude-haiku-4-5",
    ]:
        assert resolve_profile("auto", model) == LEAN_PROFILE, model


def test_auto_does_not_read_a_large_declared_size_as_small():
    """The size rule accepts 1-14B only; bigger stated counts stay terse."""
    for model in ["qwen3-32b", "llama-3-70b", "llama-3.1-405b"]:
        assert resolve_profile("auto", model) == FULL_PROFILE, model


def test_flash_is_a_latency_tier_not_a_size_and_stays_full():
    """`flash` spans weak to strong, so it is opt-in rather than a default."""
    assert resolve_profile("auto", "gemini-2.5-flash") == FULL_PROFILE
    assert resolve_profile("auto", "deepseek:deepseek-v4-flash") == FULL_PROFILE
    register_model_profile("deepseek-v4-flash", "lean")
    assert resolve_profile("auto", "deepseek:deepseek-v4-flash") == LEAN_PROFILE


def test_a_user_declaration_overrides_a_built_in_default():
    register_model_profile("qwen2.5-7b", "full")
    assert resolve_profile("auto", "ollama:qwen2.5-7b") == FULL_PROFILE


def test_built_in_defaults_survive_clearing_user_declarations():
    model_profile_registry.clear()
    assert resolve_profile("auto", "ollama:qwen2.5-7b") == LEAN_PROFILE


def test_a_registry_without_defaults_matches_nothing():
    from zrb.llm.prompt.profile import ModelProfileRegistry

    isolated = ModelProfileRegistry(defaults=())
    assert isolated.resolve("ollama:qwen2.5-7b") is None
    isolated.set("qwen2.5-7b", "lean")
    assert isolated.resolve("ollama:qwen2.5-7b") == LEAN_PROFILE


def test_none_or_blank_profile_behaves_like_auto():
    assert resolve_profile(None, "deepseek-v4") == FULL_PROFILE
    assert resolve_profile("", "claude-opus") == FULL_PROFILE


def test_unknown_profile_value_falls_through_to_auto():
    assert resolve_profile("bogus", "claude-opus") == FULL_PROFILE


def test_declared_mapping_drives_auto_resolution():
    register_model_profile("my-tiny-7b", "lean")
    assert resolve_profile("auto", "ollama:my-tiny-7b") == LEAN_PROFILE
    # A non-matching model is unaffected.
    assert resolve_profile("auto", "anthropic:claude-opus-4") == FULL_PROFILE


def test_declared_mapping_matches_model_object():
    register_model_profile(r"gemma-2-9b", "lean")
    assert resolve_profile("auto", _Model("ollama:gemma-2-9b")) == LEAN_PROFILE


def test_pattern_matches_full_id_without_stripping_any_segment():
    # The full id is matched as-is — provider, model, and tier all visible.
    cloud_model = "ollama:deepseek-v4-flash:cloud"
    # A model-name substring matches (and is NOT reduced to just "cloud").
    register_model_profile("deepseek-v4-flash", "lean")
    assert resolve_profile("auto", cloud_model) == LEAN_PROFILE


def test_pattern_can_match_provider_or_tier():
    register_model_profile(r"^ollama:", "lean")
    assert resolve_profile("auto", "ollama:anything:cloud") == LEAN_PROFILE
    assert resolve_profile("auto", "anthropic:claude-opus-4") == FULL_PROFILE


def test_most_recent_declaration_wins():
    register_model_profile("foo", "full")
    register_model_profile("foo", "lean")
    assert resolve_profile("auto", "foo-model") == LEAN_PROFILE


def test_lean_knob_overrides_a_full_declaration():
    register_model_profile("foo", "full")
    # The explicit knob is authoritative; declarations only feed auto.
    assert resolve_profile("lean", "foo-model") == LEAN_PROFILE


def test_set_rejects_invalid_profile():
    with pytest.raises(ValueError):
        model_profile_registry.set("foo", "verbose")


def test_isolated_registry_instance_does_not_touch_singleton():
    isolated = ModelProfileRegistry()
    isolated.set("foo", "lean")
    assert isolated.resolve("foo-model") == LEAN_PROFILE
    # Singleton remains empty.
    assert model_profile_registry.resolve("foo-model") is None


def test_the_old_explicit_value_is_no_longer_a_profile():
    """`explicit` was renamed to `lean` with no alias (ADR-0047)."""
    # An unrecognized ZRB_LLM_PROFILE falls through to auto-resolution.
    assert resolve_profile("explicit", "anthropic:claude-opus-4") == FULL_PROFILE
    with pytest.raises(ValueError, match="Unknown profile"):
        register_model_profile("legacy-model", "explicit")


# ── Presets (ADR-0075) ──────────────────────────────────────────────────


def test_auto_selects_minimal_only_from_a_declared_size_of_4b_or_less():
    for model in ["ollama:qwen2.5:3b", "ollama:llama3.2:3B", "local/phi-2b", "tiny-1b"]:
        assert resolve_profile("auto", model) == MINIMAL_PROFILE, model


def test_the_size_bands_do_not_overlap():
    """5B-14B stays on `lean`; `minimal` must not swallow the band above it."""
    for model in ["mistral-7b", "gemma-2-9b", "qwen2.5-14b"]:
        assert resolve_profile("auto", model) == LEAN_PROFILE, model
    for model in ["qwen2.5-32b", "llama-3-70b", "deepseek-405b"]:
        assert resolve_profile("auto", model) == FULL_PROFILE, model


def test_vendor_small_tier_labels_stay_on_lean():
    """`minimal` removes capability, so a label is never enough to select it.

    `lean` keeps every section and tool, so a false positive is cheap.
    `minimal` drops both, so a false positive is expensive — and `nano`/`tiny`
    label models (`gpt-5-nano`) far more capable than a 3B local one.

    `micro` is in the list for the same reason, and is the case the old naming
    got wrong: while a preset was *called* `micro`, a model labelled `-micro`
    matched no pattern at all and fell through to the heaviest preset.
    """
    for model in [
        "openai:gpt-5-nano",
        "openai:gpt-5-mini",
        "openai:gpt-5-micro",
        "anthropic:claude-haiku-4-5",
    ]:
        assert resolve_profile("auto", model) == LEAN_PROFILE, model


def test_a_user_declaration_can_still_force_minimal():
    register_model_profile("my-local-model", MINIMAL_PROFILE)
    assert resolve_profile("auto", "my-local-model") == MINIMAL_PROFILE


def test_full_constrains_nothing():
    """`full` is the unconstrained baseline every other preset subtracts from."""
    preset = resolve_preset(FULL_PROFILE)
    assert (preset.sections, preset.variant, preset.tools) == (None, None, None)


def test_only_minimal_constrains_the_tool_axis():
    """`lean` keeps every capability; it lightens the rulebook, not the surface.

    A 5-14B model can still use skills, todos and delegation, so trimming its
    tools would cost behaviour rather than burden. Only `minimal` goes that far.
    """
    assert resolve_preset(LEAN_PROFILE).tools is None
    assert resolve_preset(MINIMAL_PROFILE).tools == MINIMAL_TOOLS


def test_lean_reshapes_only_the_phrasing_axis():
    """`lean` keeps every section and tool; the variant does all the work.

    Its lighter rulebook is `workflow.lean.md`, resolved through the same
    `{section}.{profile}.md` convention as `examples.lean.md`. Constraining the
    section list would be a second way to say the same thing.
    """
    preset = resolve_preset(LEAN_PROFILE)
    assert preset.variant == LEAN_PROFILE
    assert preset.sections is None
    assert preset.tools is None


def test_minimal_binds_all_three_axes():
    """`minimal` is the only preset that constrains sections and tools."""
    preset = resolve_preset(MINIMAL_PROFILE)
    assert preset.sections == MINIMAL_SECTIONS
    assert preset.tools == MINIMAL_TOOLS
    assert preset.variant == MINIMAL_PROFILE


def test_minimal_drops_sections_rather_than_renaming_them():
    """`workflow` stays the section name at every preset.

    A preset varies a section's *text* through the variant axis, so the section
    list only ever says which topics appear. A `workflow_minimal` entry would
    fork the vocabulary the composition tests police.
    """
    assert "workflow" in MINIMAL_SECTIONS
    assert not any(name.startswith("workflow_") for name in MINIMAL_SECTIONS)


def test_an_unknown_profile_degrades_to_the_full_surface():
    """A stale config must lose nothing rather than land on a crippled preset."""
    preset = resolve_preset("no-such-profile")
    assert (preset.sections, preset.variant, preset.tools) == (None, None, None)


def test_a_user_can_register_a_fourth_preset():
    """`PRESETS` is the source of truth for the valid set, so a dict entry is enough."""
    PRESETS["nano"] = Preset(sections=("persona",), tools=frozenset({"Read"}))
    try:
        assert "nano" in valid_profiles()
        assert resolve_profile("nano", "anything") == "nano"
        register_model_profile("my-nano-box", "nano")
        assert resolve_profile("auto", "my-nano-box") == "nano"
    finally:
        del PRESETS["nano"]
