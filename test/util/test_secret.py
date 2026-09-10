"""Name-based redaction for values that must not reach a log."""

import pytest

from zrb.config.config import CFG
from zrb.util.secret import SECRET_MASK, is_secret_env_name, redact_env_map

PATTERNS = ["KEY", "SECRET", "TOKEN", "PASSWORD"]


@pytest.mark.parametrize(
    "name",
    [
        "OPENAI_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "TELEGRAM_BOT_TOKEN",
        "MY_DB_PASSWORD",
        "openai_api_key",  # matching is case-insensitive
        "key",  # ...and matches the whole name too
    ],
)
def test_credential_looking_names_are_detected(name):
    assert is_secret_env_name(name, PATTERNS)


@pytest.mark.parametrize("name", ["HOME", "PATH", "LANG", "ZRB_LOGGING_LEVEL"])
def test_ordinary_names_are_left_alone(name):
    assert not is_secret_env_name(name, PATTERNS)


def test_redact_masks_values_but_keeps_names():
    """Knowing `OPENAI_API_KEY` was set is the useful half of a debug dump;
    the value is the half that must not be in a pasted bug report."""
    redacted = redact_env_map(
        {"OPENAI_API_KEY": "sk-live-abc", "HOME": "/home/u"}, PATTERNS
    )
    assert redacted == {"OPENAI_API_KEY": SECRET_MASK, "HOME": "/home/u"}


def test_redact_does_not_mutate_its_input():
    env = {"MY_TOKEN": "abc"}
    redact_env_map(env, PATTERNS)
    assert env == {"MY_TOKEN": "abc"}


def test_an_empty_pattern_list_redacts_nothing():
    """`SECRET_ENV_PATTERNS=""` is the documented opt-out."""
    env = {"OPENAI_API_KEY": "sk-live-abc"}
    assert redact_env_map(env, []) == env


def test_an_empty_pattern_string_does_not_match_everything():
    """`"".upper() in anything` is always True — the guard against a stray
    empty entry (a trailing comma in the env var) masking the whole map."""
    assert not is_secret_env_name("HOME", [""])


def test_the_shipped_default_patterns_cover_the_common_providers():
    """The defaults are what protect a user who never configures this."""
    patterns = CFG.SECRET_ENV_PATTERNS
    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "TELEGRAM_BOT_TOKEN",
        "DB_PASSWORD",
        "GITHUB_TOKEN",
    ):
        assert is_secret_env_name(name, patterns), name
    assert not is_secret_env_name("PATH", patterns)
