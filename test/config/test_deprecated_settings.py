"""A renamed setting keeps reading its old name, and says so once.

`zrb` renames knobs (this pass moved every `ENABLE_<x>` and bare switch to
`<x>_ENABLED`). An environment file or a `zrb_init.py` written before the
rename must keep working, which is why the old name is an alias rather than a
retired name: a value read from it is the value in effect, and the only cost is
one warning line.
"""

import logging
import os

import pytest

from zrb.config.config import CFG


@pytest.fixture
def clean_env(monkeypatch):
    """Drop both spellings so the test's own value is the only one."""
    monkeypatch.delenv("ZRB_LLM_REWIND_ENABLED", raising=False)
    monkeypatch.delenv("ZRB_LLM_ENABLE_REWIND", raising=False)
    return monkeypatch


def test_the_old_environment_name_still_sets_the_value(clean_env):
    clean_env.setenv("ZRB_LLM_ENABLE_REWIND", "off")

    assert CFG.LLM_REWIND_ENABLED is False


def test_the_new_environment_name_wins_when_both_are_set(clean_env):
    clean_env.setenv("ZRB_LLM_ENABLE_REWIND", "off")
    clean_env.setenv("ZRB_LLM_REWIND_ENABLED", "on")

    assert CFG.LLM_REWIND_ENABLED is True


def test_reading_the_old_name_warns_once_and_names_the_new_one(
    clean_env, caplog, monkeypatch
):
    field = CFG.get_settable_field("LLM_REWIND_ENABLED")
    monkeypatch.setattr(field, "_warned_deprecated", set())
    clean_env.setenv("ZRB_LLM_ENABLE_REWIND", "on")
    caplog.set_level(logging.WARNING)

    for _ in range(3):
        assert CFG.LLM_REWIND_ENABLED is True

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == [
        "ZRB_LLM_ENABLE_REWIND is deprecated; use ZRB_LLM_REWIND_ENABLED instead."
    ]


def test_the_new_name_alone_warns_nothing(clean_env, caplog):
    clean_env.setenv("ZRB_LLM_REWIND_ENABLED", "on")
    caplog.set_level(logging.WARNING)

    assert CFG.LLM_REWIND_ENABLED is True

    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


def test_the_deprecated_report_names_every_old_variable_that_is_set(clean_env):
    clean_env.setenv("ZRB_LLM_ENABLE_REWIND", "on")

    assert CFG.get_deprecated_env_keys() == {
        "ZRB_LLM_ENABLE_REWIND": "ZRB_LLM_REWIND_ENABLED"
    }


def test_a_deprecated_name_is_not_reported_as_a_typo(clean_env):
    clean_env.setenv("ZRB_LLM_ENABLE_REWIND", "on")

    assert "ZRB_LLM_ENABLE_REWIND" not in CFG.get_mistyped_env_keys()


def test_the_old_attribute_reads_the_new_one(clean_env, caplog):
    clean_env.setenv("ZRB_LLM_REWIND_ENABLED", "on")
    caplog.set_level(logging.WARNING)

    assert CFG.LLM_ENABLE_REWIND is True


def test_assigning_the_old_attribute_writes_the_new_one(clean_env):
    clean_env.delenv("ZRB_LLM_REWIND_ENABLED", raising=False)

    CFG.LLM_ENABLE_REWIND = False

    assert os.environ["ZRB_LLM_REWIND_ENABLED"] == "off"
    assert "ZRB_LLM_ENABLE_REWIND" not in os.environ


def test_a_renamed_setting_is_not_a_typo_but_an_unknown_one_still_is(clean_env):
    clean_env.setenv("ZRB_LLM_ENABLE_REWIND", "on")

    assert "ZRB_LLM_ENABLE_REWIND" not in CFG.get_mistyped_env_keys()
    with pytest.raises(AttributeError):
        _ = CFG.LLM_NOT_A_SETTING
