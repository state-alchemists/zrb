"""The three conditions that need no checkout: version, setting and date.

A `file:` condition has to be anchored to a tree, so it lives in
`test_journal_expiry.py` with the path rules. These three are answered from what
this build already knows about itself, anywhere — including a session opened
outside any repository — so the interesting part is not where they are read but
when they are allowed to answer "cannot tell".

They are a file of their own because the file-condition tests had reached the
500-line split rule, and "which repository am I in" is not a question these ask.
"""

from datetime import date, timedelta

import pytest

from zrb.llm.tool.journal_expiry import is_condition_met, parse_condition


@pytest.mark.parametrize(
    "condition, version, expected",
    [
        ("version:>=3.29", "3.29.1", True),
        ("version:>=3.29", "3.28.0", False),
        ("version:<3.30", "3.29.1", True),
        ("version:=3.29", "3.29.0", True),
        ("version:3.29", "3.29.0", True),
        ("version:>3.29", "3.29.0", False),
        ("version:>=3.29", "", None),
        # PEP 440 segments: a development build is older than the release it is
        # building, a postrelease is newer, and a local build sorts after its base.
        ("version:<3.29", "3.29.0.dev1", True),
        ("version:<3.29", "3.29.0rc1", True),
        ("version:>=3.29", "3.29.0.post1", True),
        ("version:>=3.29", "3.29.0+local.1", True),
        ("version:>=3.29.0rc1", "3.29.0rc2", True),
        ("version:<3.29.0rc1", "3.29.0b1", True),
    ],
)
def test_a_version_condition_compares_the_numbers_it_names(condition, version, expected):
    assert is_condition_met(parse_condition(condition), "", version) is expected


def test_a_version_condition_that_is_not_a_version_is_uncheckable():
    assert is_condition_met(parse_condition("version:latest"), "", "3.29") is None


def test_a_setting_condition_compares_the_configured_token(monkeypatch):
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_JOURNAL_ENABLED", True, raising=False)

    on = parse_condition("setting:LLM_JOURNAL_ENABLED=on")
    off = parse_condition("setting:LLM_JOURNAL_ENABLED=off")
    assert is_condition_met(on, "", "3.29") is True
    assert is_condition_met(off, "", "3.29") is False


def test_a_setting_this_build_does_not_carry_is_uncheckable():
    condition = parse_condition("setting:NO_SUCH_SETTING=on")

    assert is_condition_met(condition, "", "3.29") is None


def test_a_date_condition_holds_through_its_own_day():
    today = date.today()

    assert (
        is_condition_met(parse_condition(f"date:{today.isoformat()}"), "", "3") is True
    )
    yesterday = (today - timedelta(days=1)).isoformat()
    assert is_condition_met(parse_condition(f"date:{yesterday}"), "", "3") is False


def test_a_date_condition_that_is_not_a_date_is_uncheckable():
    assert is_condition_met(parse_condition("date:someday"), "", "3") is None
