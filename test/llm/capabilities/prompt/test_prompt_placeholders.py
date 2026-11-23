"""A prompt may name a limit, and it renders the value the setting holds now."""

import pytest

import zrb.llm.contracts.shared.prompt_text as prompt_text
from zrb.config.config import CFG
from zrb.llm.contracts.shared.prompt_text import _fill_cfg_placeholders, get_prompt


def test_a_prompt_may_name_any_numeric_setting(monkeypatch):
    """The limits that work are the ones a prompt names, not a list kept here."""
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIARY_MAX_CHARS", 12_000, raising=False)
    assert (
        _fill_cfg_placeholders("a page of {CFG_LLM_MEMORY_DIARY_MAX_CHARS} characters")
        == "a page of 12000 characters"
    )


def test_a_prompt_may_name_a_float_setting(monkeypatch):
    """A timeout is a float as often as a count is an int, and both are limits."""
    monkeypatch.setattr(CFG, "LLM_THROTTLE_SLEEP", 2.0, raising=False)
    assert (
        _fill_cfg_placeholders("sleep {CFG_LLM_THROTTLE_SLEEP} seconds")
        == "sleep 2.0 seconds"
    )


def test_a_switch_renders_as_its_own_name(monkeypatch):
    """A bool is an int to Python; it must still read as `True`, not as `1`."""
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", True, raising=False)
    assert _fill_cfg_placeholders("{CFG_LLM_MEMORY_ENABLED}") == "True"


def test_a_string_setting_is_left_as_written(monkeypatch):
    """A prompt is sent to the provider and kept, so a string here is a disclosure.

    The resolver's rule is the value's type: a limit goes stale and is worth
    naming, while a credential is a string and must not be reachable from a
    repository's prompt override.
    """
    monkeypatch.setattr(
        CFG, "LLM_ASSISTANT_NAME", "A secret is a string", raising=False
    )
    text = "{CFG_LLM_ASSISTANT_NAME}"
    assert _fill_cfg_placeholders(text) == text


def test_a_name_the_config_does_not_have_is_left_as_written():
    """A placeholder emptied by a typo reads as a hole in a sentence, and silently."""
    text = "a page of {CFG_LLM_MEMORY_DIARY_MAX_CHARZ} characters"
    assert _fill_cfg_placeholders(text) == text


def test_a_prompt_with_no_placeholder_is_returned_untouched():
    text = "No setting is named here, and no brace stands in for one."
    assert _fill_cfg_placeholders(text) == text


def test_get_prompt_fills_the_setting_its_text_names(monkeypatch):
    """The wiring, not just the helper: `get_prompt` is where a prompt is rendered."""
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIARY_COMPACT_AT", 10_000, raising=False)
    monkeypatch.setattr(
        prompt_text,
        "_load_prompt_for_profile",
        lambda name, profile: "compacted from {CFG_LLM_MEMORY_DIARY_COMPACT_AT}",
    )
    assert get_prompt("probe") == "compacted from 10000"


def test_a_caller_still_overrides_a_setting_the_prompt_names(monkeypatch):
    """An argument to `get_prompt` beats the setting it answers, as it always did."""
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIARY_MAX_CHARS", 12_000, raising=False)
    monkeypatch.setattr(
        prompt_text,
        "_load_prompt_for_profile",
        lambda name, profile: "a page of {CFG_LLM_MEMORY_DIARY_MAX_CHARS}",
    )
    assert (
        get_prompt("probe", CFG_LLM_MEMORY_DIARY_MAX_CHARS="mine") == "a page of mine"
    )


@pytest.mark.parametrize("key", ["ROOT_GROUP_NAME", "LLM_ASSISTANT_NAME", "ENV_PREFIX"])
def test_the_three_names_that_worked_before_still_work(key, monkeypatch):
    """Widening the resolver is not a change to the placeholders already in use."""
    monkeypatch.setattr(
        prompt_text, "_load_prompt_for_profile", lambda name, profile: f"{{CFG_{key}}}"
    )
    rendered = get_prompt("probe")
    if getattr(CFG, key) is not None:
        assert f"{{CFG_{key}}}" not in rendered
        assert rendered == str(getattr(CFG, key))
