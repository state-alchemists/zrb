"""What `applies_when` can be checked against, and what it is allowed to conclude.

`applies_when` gave a note an end, but almost every value is prose, and nothing
can check a sentence. These tests pin the narrow subset that can be checked — a
file's content, zrb's version, a setting, a date — and the rule that governs
everything else: a condition this machine cannot evaluate keeps its note. Expiry
removes what is *disproved*, never what is merely unchecked.
"""

from datetime import date, datetime, timedelta

import pytest

from zrb.llm.tool.journal_expiry import (
    Condition,
    expired_note_rels,
    file_sha,
    is_condition_met,
    parse_condition,
    stamp,
)
from zrb.llm.tool.journal_note import Note


def _note(rel: str, applies_when: str, repo: str = "zrb") -> Note:
    return Note(
        category=rel.split("/")[0],
        slug=rel.split("/")[-1].removesuffix(".md"),
        title=rel,
        status="active",
        hud_line="a line",
        pinned=False,
        updated=datetime(2026, 11, 1),
        has_stamp=True,
        repo=repo,
        applies_when=applies_when,
    )


def test_each_prefix_is_read_as_its_own_kind():
    assert parse_condition("file:src/a.py@abc") == Condition("file", "src/a.py@abc")
    assert parse_condition("version:>=3.29") == Condition("version", ">=3.29")
    assert parse_condition("setting:LLM_ENABLED=on") == Condition(
        "setting", "LLM_ENABLED=on"
    )
    assert parse_condition("date:2026-12-01") == Condition("date", "2026-12-01")


def test_the_prefix_is_read_whatever_its_case():
    assert parse_condition("FILE:src/a.py@abc") == Condition("file", "src/a.py@abc")


@pytest.mark.parametrize(
    "prose",
    [
        "while zrb 3.29 is the released line",
        "while go uses the office laptop",
        "not stated",
        "",
        "   ",
    ],
)
def test_a_sentence_is_not_a_condition(prose):
    """Guessing that a sentence is false would retire a note its author still
    believes, which is worse than the note staying."""
    assert parse_condition(prose) is None


def test_a_prefix_with_no_payload_is_not_a_condition():
    assert parse_condition("file:") is None


def test_stamping_records_the_hash_of_the_file_as_it_is_now(tmp_path):
    target = tmp_path / "settings.py"
    target.write_text("retries = 1\n", encoding="utf-8")

    assert stamp("file:settings.py", str(tmp_path)) == (
        f"file:settings.py@{file_sha(str(target))}"
    )


def test_a_changed_file_no_longer_matches_its_stamp(tmp_path):
    target = tmp_path / "settings.py"
    target.write_text("retries = 1\n", encoding="utf-8")
    stamped = stamp("file:settings.py", str(tmp_path))
    target.write_text("retries = 3\n", encoding="utf-8")

    condition = parse_condition(stamped)
    assert is_condition_met(condition, str(tmp_path), "3.29", "zrb") is False


def test_a_stamp_is_not_replaced_by_a_later_write(tmp_path):
    """The hash says what the note was written against; re-stamping would make
    every revision silently renew a condition that had stopped holding."""
    target = tmp_path / "settings.py"
    target.write_text("retries = 1\n", encoding="utf-8")
    first = stamp("file:settings.py", str(tmp_path))
    target.write_text("retries = 3\n", encoding="utf-8")

    assert stamp(first, str(tmp_path)) == first


def test_stamping_needs_a_repository_to_be_relative_to(tmp_path):
    """A hash taken from the process's own directory would point at whatever sits
    beside a later reader; unstamped reads as uncheckable and keeps the note."""
    (tmp_path / "settings.py").write_text("x\n", encoding="utf-8")

    assert stamp("file:settings.py", "") == "file:settings.py"


def test_a_file_with_no_stamp_is_uncheckable(tmp_path):
    (tmp_path / "settings.py").write_text("x\n", encoding="utf-8")

    condition = Condition("file", "settings.py")
    assert is_condition_met(condition, str(tmp_path), "3.29", "zrb") is None


def test_a_missing_file_is_a_change_not_an_inability(tmp_path):
    condition = Condition("file", "gone.py@abc123")

    assert is_condition_met(condition, str(tmp_path), "3.29", "zrb") is False


def test_a_file_condition_is_not_checked_from_another_repository(tmp_path):
    """The same relative path in another checkout is another file, so the answer
    there would be about the wrong file — and a false answer retires the note."""
    condition = Condition("file", "settings.py@abc123")

    assert is_condition_met(condition, str(tmp_path), "3.29", "") is None


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
    ],
)
def test_a_version_condition_compares_the_numbers_it_names(condition, version, expected):
    assert is_condition_met(parse_condition(condition), "", version, "zrb") is expected


def test_a_version_condition_that_is_not_a_version_is_uncheckable():
    assert is_condition_met(parse_condition("version:latest"), "", "3.29", "zrb") is None


def test_a_setting_condition_compares_the_configured_token(monkeypatch):
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_JOURNAL_ENABLED", True, raising=False)

    on = parse_condition("setting:LLM_JOURNAL_ENABLED=on")
    off = parse_condition("setting:LLM_JOURNAL_ENABLED=off")
    assert is_condition_met(on, "", "3.29", "zrb") is True
    assert is_condition_met(off, "", "3.29", "zrb") is False


def test_a_setting_this_build_does_not_carry_is_uncheckable():
    condition = parse_condition("setting:NO_SUCH_SETTING=on")

    assert is_condition_met(condition, "", "3.29", "zrb") is None


def test_a_date_condition_holds_through_its_own_day():
    today = date.today()

    assert is_condition_met(parse_condition(f"date:{today.isoformat()}"), "", "3", "zrb") is True
    yesterday = (today - timedelta(days=1)).isoformat()
    assert is_condition_met(parse_condition(f"date:{yesterday}"), "", "3", "zrb") is False


def test_a_date_condition_that_is_not_a_date_is_uncheckable():
    assert is_condition_met(parse_condition("date:someday"), "", "3", "zrb") is None


def test_prose_never_expires():
    notes = [_note("technical/a.md", "while zrb 3.29 is the released line")]

    assert expired_note_rels(notes, "", "zrb", "3.29") == set()


def test_a_disproved_version_expires_the_note():
    notes = [_note("technical/a.md", "version:<3.29")]

    assert expired_note_rels(notes, "", "zrb", "3.29") == {"technical/a.md"}


def test_another_repositorys_file_condition_is_not_checked(tmp_path):
    """`root` names this checkout's tree; another repository's file is not in it."""
    (tmp_path / "settings.py").write_text("x\n", encoding="utf-8")
    notes = [_note("technical/a.md", "file:settings.py@deadbeef", repo="soda")]

    assert expired_note_rels(notes, str(tmp_path), "zrb", "3.29") == set()


def test_a_proved_file_expires_and_an_unstamped_one_does_not(tmp_path):
    target = tmp_path / "settings.py"
    target.write_text("retries = 1\n", encoding="utf-8")
    stamped = stamp("file:settings.py", str(tmp_path))
    target.write_text("retries = 3\n", encoding="utf-8")
    notes = [
        _note("technical/changed.md", stamped),
        _note("technical/unstamped.md", "file:settings.py"),
    ]

    assert expired_note_rels(notes, str(tmp_path), "zrb", "3.29") == {
        "technical/changed.md"
    }
