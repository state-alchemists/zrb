"""Tests for model-adaptive prompt profiles and presets (ADR-0049)."""

import logging

import pytest

from zrb.llm.prompt.profile import (
    FULL_PROFILE,
    LEAN_DROPS,
    LEAN_PROFILE,
    MINIMAL_PROFILE,
    MINIMAL_SECTIONS,
    MINIMAL_TOOLS,
    PRESETS,
    ModelProfileRegistry,
    Preset,
    active_preset,
    builtin_profile,
    model_profile_registry,
    register_model_profile,
    register_preset,
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
    # A family name is still never read as a capability signal (ADR-0049):
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
    """The size rule accepts 1-14B only; bigger stated counts stay `full`."""
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


def test_a_model_declaring_nothing_resolves_to_nothing():
    """`resolve` reports "no opinion" rather than guessing, so `auto` can fall back."""
    isolated = ModelProfileRegistry()
    assert isolated.resolve("ollama:some-model") is None
    isolated.set("some-model", "lean")
    assert isolated.resolve("ollama:some-model") == LEAN_PROFILE


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
    """`explicit` was renamed to `lean` with no alias (ADR-0049)."""
    # An unrecognized ZRB_LLM_PROFILE falls through to auto-resolution.
    assert resolve_profile("explicit", "anthropic:claude-opus-4") == FULL_PROFILE
    with pytest.raises(ValueError, match="Unknown profile"):
        register_model_profile("legacy-model", "explicit")


# ── Presets (ADR-0049) ──────────────────────────────────────────────────


def test_auto_selects_minimal_only_from_a_declared_size_of_4b_or_less():
    for model in ["ollama:qwen2.5:3b", "ollama:llama3.2:3B", "local/phi-2b", "tiny-1b"]:
        assert resolve_profile("auto", model) == MINIMAL_PROFILE, model


def test_a_fractional_parameter_count_reads_as_one_number():
    """`1.5b` is 1.5B, not 5B — the case a per-band digit class got wrong.

    `deepseek-r1:1.5b` and `qwen2.5:0.5b` are the two most common local models
    on the planet, and both landed on `lean` (the 5-14B preset) because the
    digit before the `b` was read in isolation. A stated size is parsed as a
    number now, so the decimal is part of it.
    """
    for model in ["ollama:deepseek-r1:1.5b", "ollama:qwen2.5:0.5b", "phi3:3.8b"]:
        assert resolve_profile("auto", model) == MINIMAL_PROFILE, model


def test_the_first_declared_count_is_the_one_read():
    """A model stating two sizes (`qwen3-30b-a3b`) is stating the larger first.

    An MoE id names total parameters before active ones. Reading the trailing
    `a3b` would hand a 30B model the ~3B preset; the leading count is both the
    conservative choice and the one vendors put first.
    """
    assert resolve_profile("auto", "ollama:qwen3-30b-a3b") == FULL_PROFILE


def test_a_declared_size_outranks_a_small_tier_label():
    """The count is the more specific claim, so it wins where both appear."""
    assert resolve_profile("auto", "some-mini-32b") == FULL_PROFILE
    assert resolve_profile("auto", "some-mini-3b") == MINIMAL_PROFILE


def test_the_size_bands_do_not_overlap():
    """5B-14B stays on `lean`; `minimal` must not swallow the band above it."""
    for model in ["mistral-7b", "gemma-2-9b", "qwen2.5-14b"]:
        assert resolve_profile("auto", model) == LEAN_PROFILE, model
    for model in ["qwen2.5-32b", "llama-3-70b", "deepseek-405b"]:
        assert resolve_profile("auto", model) == FULL_PROFILE, model


def test_a_hosted_small_tier_label_stays_on_lean():
    """A vendor tier name is a claim about a lineup, not about a size.

    `lean` keeps every section and tool, so a false positive is cheap; `minimal`
    drops both, so a false positive is expensive — and `nano`/`micro` label
    models (`gpt-5-nano`) far more capable than a 3B local one.

    `micro` is in the list for the same reason, and is the case the old naming
    got wrong: while a preset was *called* `micro`, a model labelled `-micro`
    matched no pattern at all and fell through to the heaviest preset.
    """
    for model in [
        "openai:gpt-5-nano",
        "openai:gpt-5-mini",
        "openai:gpt-5-micro",
        "openai:gpt-4o-mini",
        "anthropic:claude-haiku-4-5",
    ]:
        assert resolve_profile("auto", model) == LEAN_PROFILE, model


def test_a_locally_served_small_tier_label_selects_minimal():
    """The same label means a different size once you know who is serving it.

    `ollama:phi4-mini` is 3.8B of weights on the user's laptop; `openai:gpt-5-nano`
    is the entry tier of a hosted lineup. Both state no parameter count and both
    used to resolve to `lean`, handing a 3.8B model the heaviest composition in
    the system. The provider prefix is the disambiguator, and `_model_id` already
    keeps it intact.
    """
    for model in [
        "ollama:phi4-mini:latest",
        "lmstudio:phi-4-mini",
        "llamacpp:qwen2.5-mini",
        "localai:tiny-llama",
    ]:
        assert resolve_profile("auto", model) == MINIMAL_PROFILE, model


def test_ollamas_hosted_tier_is_not_treated_as_local():
    """`ollama:` also prefixes frontier models; `:cloud` is what separates them."""
    for model in [
        "ollama:kimi-k2.6:cloud",
        "ollama:qwen3-coder-next:cloud",
        "ollama:minimax-m2.7:cloud",
    ]:
        assert resolve_profile("auto", model) == FULL_PROFILE, model


def test_a_declared_size_still_outranks_a_local_prefix():
    """A stated count is the specific claim wherever the model is served."""
    assert resolve_profile("auto", "ollama:qwen3:8b") == LEAN_PROFILE
    assert resolve_profile("auto", "ollama:qwen2.5-mini:32b") == FULL_PROFILE


def test_a_user_declaration_can_still_force_minimal():
    register_model_profile("my-local-model", MINIMAL_PROFILE)
    assert resolve_profile("auto", "my-local-model") == MINIMAL_PROFILE


def test_full_constrains_nothing():
    """`full` is the unconstrained baseline every other preset subtracts from."""
    preset = resolve_preset(FULL_PROFILE)
    assert (preset.sections, preset.variant, preset.tools, preset.drops) == (
        None,
        None,
        None,
        None,
    )


def test_lean_subtracts_tools_without_closing_the_surface():
    """`lean` uses the denylist axis, so a new tool reaches it without an edit."""
    preset = resolve_preset(LEAN_PROFILE)
    assert preset.tools is None
    assert preset.drops == LEAN_DROPS
    assert preset.constrains_tools
    assert preset.admits("Shell")
    assert preset.admits("SomeToolAddedNextRelease")


def test_minimal_closes_the_surface():
    """`minimal` uses the allowlist axis, so a new tool does *not* reach it."""
    preset = resolve_preset(MINIMAL_PROFILE)
    assert preset.drops is None
    assert preset.admits("Shell")
    assert not preset.admits("SomeToolAddedNextRelease")


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


def test_active_preset_reads_the_knob_and_the_model_together(monkeypatch):
    """The one call every consumer of the three axes makes.

    `PromptManager` (sections, phrasing) and `apply_common_tools` (tools) would
    otherwise each spell out knob-then-model resolution, which is how the two
    drift apart.
    """
    monkeypatch.setenv("ZRB_LLM_PROFILE", "minimal")
    assert active_preset("anthropic:claude-opus-4").sections == MINIMAL_SECTIONS
    monkeypatch.setenv("ZRB_LLM_PROFILE", "auto")
    assert active_preset("ollama:qwen2.5:3b").tools == MINIMAL_TOOLS
    assert active_preset("anthropic:claude-opus-4").tools is None


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


@pytest.fixture
def unregister():
    """Drop any preset a test registers, so `PRESETS` survives the module."""
    added: list[str] = []
    yield added.append
    for name in added:
        PRESETS.pop(name, None)


def test_a_preset_cannot_set_both_tool_axes():
    """`admits` reads `tools` first and ignores `drops`, so both is never what
    the caller meant.

    Rejected in ``__post_init__`` rather than in ``register_preset``, because
    ``PRESETS[name] = Preset(...)`` is still a supported way in and would walk
    straight past a check that lived only in the function.
    """
    with pytest.raises(ValueError, match="either tools .* or drops"):
        Preset(tools=frozenset({"Read"}), drops=frozenset({"Edit"}))


def test_register_preset_makes_the_name_selectable(unregister):
    unregister("nano")
    register_preset("nano", Preset(sections=("persona", "workflow"), variant="lean"))

    assert "nano" in valid_profiles()
    assert resolve_profile("nano", "anything") == "nano"
    assert resolve_preset("nano").variant == "lean"
    register_model_profile("my-1b-box", "nano")
    assert resolve_profile("auto", "my-1b-box") == "nano"


def test_register_preset_normalizes_the_name(unregister):
    unregister("nano")
    register_preset("  NaNo  ", Preset())
    assert "nano" in valid_profiles()


@pytest.mark.parametrize(
    "name, preset, message",
    [
        ("", Preset(), "non-empty string"),
        ("x", "not-a-preset", "Expected a Preset"),
        ("auto", Preset(), "reserved"),
    ],
)
def test_register_preset_rejects_what_cannot_work(name, preset, message):
    """`auto` is the interesting one: it is not a preset name but the instruction
    to derive one from the model id, so a preset stored under it is unreachable."""
    with pytest.raises(ValueError, match=message):
        register_preset(name, preset)


def test_register_preset_warns_when_a_variant_has_no_file(unregister, caplog):
    """The silent fallback, surfaced.

    ``get_prompt`` resolving ``foo.{variant}.md`` → ``foo.md`` is correct
    runtime behaviour and a trap at registration: a preset written for a 1B
    model ships it the frontier rulebook and says nothing. Warned, not raised —
    varying only some sections is legitimate, which is why `full` needs no files
    at all.
    """
    unregister("nano")
    with caplog.at_level(logging.WARNING):
        register_preset("nano", Preset(variant="nowhere"))

    assert "fall back to the base" in caplog.text
    assert "workflow.nowhere.md" in caplog.text or "persona.nowhere.md" in caplog.text


def test_register_preset_warns_when_the_safety_floor_is_gone(
    unregister, caplog, tmp_path, monkeypatch
):
    """Rank 1 is pinned for the built-ins by a hardcoded list of three names.

    `test_section_composition.py::test_every_preset_carries_the_rank_one_safety_rules`
    walks `PRESET_VARIANTS`, so a preset registered at runtime inherits none of
    that guarantee. This is where a custom one gets it.
    """
    unregister("tiny")
    (tmp_path / "persona.tiny.md").write_text("# Identity\nYou are {ASSISTANT_NAME}.")
    (tmp_path / "workflow.tiny.md").write_text("# How to Work\nRead it, edit it.")

    monkeypatch.setenv("ZRB_LLM_PROMPT_DIR", str(tmp_path))
    with caplog.at_level(logging.WARNING):
        register_preset(
            "tiny", Preset(sections=("persona", "workflow"), variant="tiny")
        )

    # All three concepts, not a sample. profile.py keeps its own copy of the
    # rank-1 table on purpose (a shared one would let one wrong regex excuse
    # both), and asserting only two of the three let the copies drift on the
    # third with nothing to catch it.
    assert "secrets" in caplog.text
    assert "tool output is not instructions" in caplog.text
    assert "confirm destructive actions" in caplog.text


def test_register_preset_is_quiet_for_a_sound_preset(unregister, caplog):
    """A preset that constrains only tools keeps the default sections and the
    base prose, so it has nothing to warn about."""
    unregister("beefy")
    with caplog.at_level(logging.WARNING):
        register_preset("beefy", Preset(drops=frozenset({"SearchJournal"})))

    assert caplog.text == ""


def test_register_preset_warns_when_no_rulebook_composes(unregister, caplog):
    """Sections that carry no rules leave the model with tools and no operating
    rules — distinct from dropping *some* rules, and worth its own message."""
    unregister("bare")
    with caplog.at_level(logging.WARNING):
        register_preset("bare", Preset(sections=("system_context",)))

    assert "no rule-carrying section" in caplog.text


# ── Why this registry is not `model_capabilities` (ADR-0038 vs ADR-0049) ──


def test_profile_and_capability_registries_key_on_different_things():
    """The two registries look alike and must not be unified.

    `ModelProfileRegistry` matches the **full** model id; `model_capabilities`
    matches the **bare** name with the `provider:` prefix stripped. That is not
    duplication, it is two different questions:

    * A capability is a property of the *weights*. `gpt-4o` accepts images
      whether it is served by `openai:` or `azure:`, so the prefix is noise —
      which is why the built-in deny patterns can be `^`-anchored.
    * A profile is a property of the *deployment*. `ollama:phi4-mini` is 3.8B
      on a laptop and `openai:gpt-5-nano` is the entry tier of a hosted family,
      so who serves it is the whole signal.

    Merging them would have to pick one key, and either choice regresses
    silently: a bare name strips `ollama:`/`:cloud` and drops every local small
    model from `minimal` back to `lean`, while a full id un-anchors
    `^claude-haiku-3$` and hands a text-only model image support.
    """
    from zrb.llm.util.capabilities import model_capabilities

    # The profile side needs the prefix: it is what distinguishes a 3.8B local
    # model from a hosted entry tier that merely shares the label.
    assert builtin_profile("ollama:phi4-mini") == MINIMAL_PROFILE
    assert builtin_profile("phi4-mini") == LEAN_PROFILE
    # ...and the tier suffix, which is what keeps hosted frontier models out.
    assert builtin_profile("ollama:kimi-k2.6:cloud") is None

    # The capability side never sees a prefix, so a provider-shaped pattern
    # cannot match there. Registering one is a silent no-op, not an override.
    model_capabilities.register("ollama:", supports_image_input=True)
    try:
        assert model_capabilities.get("ollama:phi4-mini").supports_image_input is False
    finally:
        model_capabilities.clear()
