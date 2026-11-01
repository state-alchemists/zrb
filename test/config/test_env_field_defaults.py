"""Every setting states its default, so `zrb config explain` can show it."""

import pytest

from zrb.config.config import CFG


def _numeric_settings_without_a_declared_default() -> list[str]:
    """Settings whose unset value exists only because `fallback` rescues the
    cast of the empty string, leaving `get_default` empty."""
    names = []
    for name in CFG.get_settable_field_names():
        field = CFG.get_settable_field(name)
        if field is None or field.get_default(CFG) != "":
            continue
        try:
            field.cast("")
        except (ValueError, TypeError):
            names.append(name)
    return names


@pytest.fixture
def clean_env(monkeypatch):
    for name in CFG.get_settable_field_names():
        field = CFG.get_settable_field(name)
        if field is not None:
            for key in field.get_read_keys(CFG.ENV_PREFIX):
                monkeypatch.delenv(key, raising=False)


def test_a_value_the_cast_rejects_when_empty_is_none_or_has_a_declared_default(
    clean_env,
):
    """An empty default that a numeric cast cannot read would be served by the
    field's `fallback`, which is the answer to a *bad* value. The declared
    default would then read empty in `zrb config explain` while the setting
    held 20, 3, 2.0…"""
    offenders = [
        name
        for name in _numeric_settings_without_a_declared_default()
        if getattr(CFG, name) is not None
    ]
    assert offenders == []


@pytest.mark.parametrize(
    "name, expected",
    [
        ("LLM_AGENT_MESSAGE_LIMIT", "20"),
        ("LLM_DICTATION_INTERRUPT_JUDGE_TIMEOUT", "2.0"),
        ("LLM_JOURNAL_AUTO_SEARCH_MAX_HITS", "3"),
        ("LLM_JOURNAL_CATALOG_MAX_ENTRIES", "25"),
        ("LLM_JOURNAL_COMPLIANCE_TURNS", "12"),
        ("LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION", "20"),
        ("LLM_SUBAGENT_HISTORY_RETAIN", "50"),
        ("LOGGING_FILE_BACKUP_COUNT", "3"),
        ("LOGGING_FILE_MAX_BYTES", "10485760"),
    ],
)
def test_the_default_is_declared_and_is_what_an_unset_setting_reads(
    clean_env, name, expected
):
    field = CFG.get_settable_field(name)
    assert field is not None
    assert field.get_default(CFG) == expected
    assert getattr(CFG, name) == field.cast(expected)


def test_an_invalid_value_still_reads_as_the_fallback(clean_env, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_AGENT_MESSAGE_LIMIT", "many")
    assert CFG.LLM_AGENT_MESSAGE_LIMIT == 20
