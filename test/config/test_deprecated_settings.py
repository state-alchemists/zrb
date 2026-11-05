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


# Every knob this pass renamed, mapped to the names it used to answer to. This
# table is the contract: `main` accepted every value here before the rename, so
# a row that goes missing drops a user's setting silently — the symptom is a
# knob that keeps its default while the environment file says otherwise.
RENAMED = {
    "BUILTIN_TASKS_ENABLED": ["ENABLE_BUILTIN_TASKS"],
    "TIKTOKEN_ENABLED": ["ENABLE_TIKTOKEN"],
    "LLM_BUILTIN_AGENTS_ENABLED": ["LLM_ENABLE_BUILTIN_AGENTS"],
    "LLM_BUILTIN_SKILLS_ENABLED": ["LLM_ENABLE_BUILTIN_SKILLS"],
    "LLM_REWIND_ENABLED": ["LLM_ENABLE_REWIND"],
    "LLM_TOOL_SPILL_ENABLED": ["LLM_ENABLE_TOOL_SPILL"],
    "LLM_READ_IMAGE_ENABLED": ["LLM_ENABLE_READ_IMAGE"],
    "LLM_RATE_LIMIT_ENABLED": ["LLM_ENABLE_RATE_LIMIT"],
    "LLM_CAMERA_TOOL_ENABLED": ["LLM_CAMERA_ENABLE_TOOL"],
    "LLM_SCREENSHOT_TOOL_ENABLED": ["LLM_SCREENSHOT_ENABLE_TOOL"],
    "LLM_DICTATION_ECHO_CANCEL_ENABLED": ["LLM_DICTATION_ENABLE_ECHO_CANCEL"],
    "LLM_UI_MARKDOWN_MATH_ENABLED": ["LLM_UI_ENABLE_MARKDOWN_MATH"],
    "LLM_UI_MARKDOWN_MERMAID_ENABLED": ["LLM_UI_ENABLE_MARKDOWN_MERMAID"],
    "LLM_SEARCH_HOME_ENABLED": ["LLM_SEARCH_HOME"],
    "LLM_SEARCH_PROJECT_ENABLED": ["LLM_SEARCH_PROJECT"],
    "LLM_SHOW_OLLAMA_MODELS_ENABLED": ["LLM_SHOW_OLLAMA_MODELS"],
    "LLM_SHOW_PYDANTIC_AI_MODELS_ENABLED": ["LLM_SHOW_PYDANTIC_AI_MODELS"],
    "LLM_SHOW_TOOL_CALL_DETAIL_ENABLED": ["LLM_SHOW_TOOL_CALL_DETAIL"],
    "LLM_SHOW_TOOL_CALL_RESULT_ENABLED": ["LLM_SHOW_TOOL_CALL_RESULT"],
    "SHOW_UNRECOMMENDED_COMMAND_WARNING_ENABLED": [
        "SHOW_UNRECOMMENDED_COMMAND_WARNING"
    ],
    "LLM_SANDBOX_ALLOW_ESCAPE_ENABLED": ["LLM_SANDBOX_ALLOW_ESCAPE"],
    "WEB_AUTH_SECURE_COOKIES_ENABLED": [
        "WEB_AUTH_SECURE_COOKIES",
        "WEB_ENABLE_SECURE_COOKIES",
    ],
    "LLM_UI_SHOW_RUNTIME_TIMERS_ENABLED": ["LLM_UI_SHOW_RUNTIME_TIMERS"],
    "LLM_DICTATION_DETECT_EMOTION_ENABLED": ["LLM_DICTATION_DETECT_EMOTION"],
    "LLM_DICTATION_EMOTION_OUT_OF_PROCESS_ENABLED": [
        "LLM_DICTATION_EMOTION_OUT_OF_PROCESS"
    ],
    "LLM_VOICE_MOVES_SHELL_ENABLED": ["LLM_VOICE_MOVES_SHELL"],
    "LLM_BACKGROUND_WAKE_ENABLED": ["LLM_BACKGROUND_WAKE"],
    "LLM_INJECT_PROJECT_INSTRUCTIONS_ENABLED": ["LLM_INJECT_PROJECT_INSTRUCTIONS"],
    "LLM_SPEECH_BLOCK_NOTICE_ENABLED": ["LLM_SPEECH_MISSING_BLOCK_NOTICE_ENABLED"],
}


@pytest.mark.parametrize("new_name", sorted(RENAMED))
def test_a_renamed_knob_still_answers_to_every_name_it_had(new_name):
    """A rename that forgets an old name is a user's setting dropped in silence."""
    field = CFG.get_settable_field(new_name)
    assert field is not None, f"{new_name} is in RENAMED but is not a settable knob"
    for old_name in RENAMED[new_name]:
        assert (
            old_name in field.deprecated_aliases
        ), f"{old_name} is read no more: set it and {new_name} keeps its default"
        assert CFG.get_field_renamed_from(old_name) == new_name


def _drop_env(monkeypatch, *keys):
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_the_secure_cookie_alias_from_before_the_rename_still_works(monkeypatch):
    """`WEB_ENABLE_SECURE_COOKIES` predates the rename, so it is not optional."""
    _drop_env(
        monkeypatch,
        "ZRB_WEB_AUTH_SECURE_COOKIES_ENABLED",
        "ZRB_WEB_ENABLE_SECURE_COOKIES",
    )
    monkeypatch.setenv("ZRB_WEB_ENABLE_SECURE_COOKIES", "off")

    assert CFG.WEB_AUTH_SECURE_COOKIES_ENABLED is False
    assert (
        CFG.get_deprecated_env_keys()["ZRB_WEB_ENABLE_SECURE_COOKIES"]
        == "ZRB_WEB_AUTH_SECURE_COOKIES_ENABLED"
    )


def test_the_old_tool_result_name_still_turns_the_result_on(monkeypatch):
    """This knob sat on a single line, which a sweep for the block shape missed."""
    _drop_env(
        monkeypatch,
        "ZRB_LLM_SHOW_TOOL_CALL_RESULT_ENABLED",
        "ZRB_LLM_SHOW_TOOL_CALL_RESULT",
    )
    monkeypatch.setenv("ZRB_LLM_SHOW_TOOL_CALL_RESULT", "on")

    assert CFG.LLM_SHOW_TOOL_CALL_RESULT_ENABLED is True
