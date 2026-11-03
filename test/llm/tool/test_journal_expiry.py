"""What `applies_when` can be checked against, and what it is allowed to conclude.

`applies_when` gave a note an end, but almost every value is prose, and nothing
can check a sentence. These tests pin the narrow subset that can be checked — a
file's content, zrb's version, a setting, a date — and the rule that governs
everything else: a condition this machine cannot evaluate keeps its note. Expiry
removes what is *disproved*, never what is merely unchecked.
"""

import os
import stat
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from zrb.llm.tool.journal_expiry import (
    Condition,
    condition_digest,
    expired_note_rels,
    file_sha,
    is_condition_met,
    parse_condition,
)
from zrb.llm.tool.journal_index import scope_index
from zrb.llm.tool.journal_note import Note


def _note(
    rel: str,
    applies_when: str,
    repo: str = "zrb",
    hud_line: str = "a line",
    digest: str = "",
) -> Note:
    return Note(
        category=rel.split("/")[0],
        slug=rel.split("/")[-1].removesuffix(".md"),
        title=rel,
        status="active",
        hud_line=hud_line,
        pinned=False,
        updated=datetime(2026, 11, 1),
        has_stamp=True,
        repo=repo,
        applies_when=applies_when,
        applies_when_digest=digest,
    )


def test_each_prefix_is_read_as_its_own_kind():
    assert parse_condition("file:src/a.py") == Condition("file", "src/a.py")
    assert parse_condition("version:>=3.29") == Condition("version", ">=3.29")
    assert parse_condition("setting:LLM_ENABLED=on") == Condition(
        "setting", "LLM_ENABLED=on"
    )
    assert parse_condition("date:2026-12-01") == Condition("date", "2026-12-01")


def test_the_prefix_is_read_whatever_its_case():
    assert parse_condition("FILE:src/a.py") == Condition("file", "src/a.py")


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


def test_the_digest_is_the_hash_of_the_file_as_it_is_now(tmp_path):
    target = tmp_path / "settings.py"
    target.write_text("retries = 1\n", encoding="utf-8")

    assert condition_digest("file:settings.py", str(tmp_path)) == file_sha(str(target))


def test_a_changed_file_no_longer_matches_its_digest(tmp_path):
    target = tmp_path / "settings.py"
    target.write_text("retries = 1\n", encoding="utf-8")
    digest = condition_digest("file:settings.py", str(tmp_path))
    target.write_text("retries = 3\n", encoding="utf-8")

    condition = parse_condition("file:settings.py")
    assert (
        is_condition_met(condition, str(tmp_path), "3.29", "zrb", digest) is False
    )


def test_a_digest_needs_a_repository_to_be_relative_to(tmp_path):
    """A hash taken from the process's own directory would point at whatever sits
    beside a later reader; no digest reads as uncheckable and keeps the note."""
    (tmp_path / "settings.py").write_text("x\n", encoding="utf-8")

    assert condition_digest("file:settings.py", "") == ""


def test_a_file_with_no_digest_is_uncheckable(tmp_path):
    (tmp_path / "settings.py").write_text("x\n", encoding="utf-8")

    condition = Condition("file", "settings.py")
    assert is_condition_met(condition, str(tmp_path), "3.29", "zrb") is None


def test_a_missing_file_is_a_change_not_an_inability(tmp_path):
    condition = Condition("file", "gone.py")

    assert (
        is_condition_met(condition, str(tmp_path), "3.29", "zrb", "deadbeefcafe")
        is False
    )


def test_a_file_condition_is_not_checked_from_another_repository(tmp_path):
    """The same relative path in another checkout is another file, so the answer
    there would be about the wrong file — and a false answer retires the note."""
    condition = Condition("file", "settings.py")

    assert (
        is_condition_met(condition, str(tmp_path), "3.29", "", "deadbeefcafe") is None
    )


def test_a_file_name_may_contain_an_at_sign(tmp_path):
    """`config@prod.yml` is just a path now: the digest is a field of its own, so
    there is no segment for a reader to mistake for one."""
    target = tmp_path / "config@prod.yml"
    target.write_text("mode = prod\n", encoding="utf-8")

    digest = condition_digest("file:config@prod.yml", str(tmp_path))

    assert digest == file_sha(str(target))
    condition = parse_condition("file:config@prod.yml")
    assert is_condition_met(condition, str(tmp_path), "3.29", "zrb", digest) is True


def test_a_path_that_ends_in_a_digest_is_hashed_as_the_path_it_is(tmp_path):
    """`config@deadbeefcafe` is a legal file name — the reason the digest left the
    value. This file is hashed, and `config` is never looked at."""
    target = tmp_path / "config@deadbeefcafe"
    target.write_text("mode = prod\n", encoding="utf-8")
    (tmp_path / "config").write_text("something else\n", encoding="utf-8")

    digest = condition_digest("file:config@deadbeefcafe", str(tmp_path))

    assert digest == file_sha(str(target))
    condition = parse_condition("file:config@deadbeefcafe")
    assert is_condition_met(condition, str(tmp_path), "3.29", "zrb", digest) is True


def test_a_digest_shaped_path_that_does_not_exist_yet_cannot_hide_its_note(tmp_path):
    """The path reads as a path, and a path nobody stamped is uncheckable. Reading
    its last segment as a digest would hash `config` and hide a note about a file
    that was never touched."""
    condition = parse_condition("file:config@deadbeefcafe")

    assert condition_digest("file:config@deadbeefcafe", str(tmp_path)) == ""
    assert is_condition_met(condition, str(tmp_path), "3.29", "zrb") is None


def test_an_absolute_path_is_never_read(tmp_path):
    """A condition is text a model wrote, so `file:` must not be a way to read the
    machine: `/dev/zero` blocks the turn, and nothing outside the tree is what the
    note is about."""
    assert condition_digest("file:/dev/zero", str(tmp_path)) == ""
    condition = Condition("file", "/dev/zero")

    assert (
        is_condition_met(condition, str(tmp_path), "3.29", "zrb", "deadbeefcafe")
        is None
    )


def test_a_path_cannot_climb_out_of_the_repository(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    root = tmp_path / "repo"
    root.mkdir()

    assert condition_digest("file:../outside.txt", str(root)) == ""
    condition = Condition("file", "../outside.txt")

    assert (
        is_condition_met(condition, str(root), "3.29", "zrb", file_sha(str(outside)))
        is None
    )


def test_a_symlink_out_of_the_repository_is_not_followed(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    try:
        (root / "link.txt").symlink_to(outside)
    except OSError:
        pytest.skip("this platform does not allow symlinks without elevation")

    assert condition_digest("file:link.txt", str(root)) == ""
    condition = Condition("file", "link.txt")

    assert (
        is_condition_met(condition, str(root), "3.29", "zrb", file_sha(str(outside)))
        is None
    )


def test_a_symlink_is_refused_at_the_descriptor_not_just_at_the_path(tmp_path):
    """`condition_path` resolves the path, but the file is opened by name after
    that — so a symlink swapped in between must fail the open itself. `O_NOFOLLOW`
    is what makes the guarantee hold rather than being checked and then undone."""
    if not hasattr(os, "O_NOFOLLOW"):
        pytest.skip("this platform has no O_NOFOLLOW; the resolved-path check is the only guard")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("this platform does not allow symlinks without elevation")

    assert file_sha(str(link)) == ""


def test_a_symlink_inside_the_tree_still_names_the_file_it_points_at(tmp_path):
    """The rule is about where the file ends up, not about refusing links: one that
    stays inside the repository is the note's own file."""
    root = tmp_path / "repo"
    root.mkdir()
    real = root / "real.txt"
    real.write_text("mode = prod\n", encoding="utf-8")
    try:
        (root / "link.txt").symlink_to(real)
    except OSError:
        pytest.skip("this platform does not allow symlinks without elevation")

    digest = condition_digest("file:link.txt", str(root))

    assert digest == file_sha(str(real))
    assert (
        is_condition_met(
            parse_condition("file:link.txt"), str(root), "3.29", "zrb", digest
        )
        is True
    )


def test_a_directory_and_an_oversized_file_are_uncheckable(tmp_path, monkeypatch):
    """Neither is what a condition names, and neither is worth reading whole."""
    from zrb.llm.tool import journal_expiry

    (tmp_path / "src").mkdir()
    (tmp_path / "big.py").write_text("x" * 17, encoding="utf-8")
    monkeypatch.setattr(journal_expiry, "MAX_HASH_BYTES", 16)

    assert condition_digest("file:src", str(tmp_path)) == ""
    assert condition_digest("file:big.py", str(tmp_path)) == ""
    for value in ("src", "big.py"):
        condition = Condition("file", value)
        assert (
            is_condition_met(condition, str(tmp_path), "3.29", "zrb", "deadbeefcafe")
            is None
        )


def test_a_file_that_grows_during_the_read_is_uncheckable(tmp_path, monkeypatch):
    """`fstat` bounds the read, but a file can grow between the two. What was read
    is then part of the file, and a digest of that part is not evidence of
    anything — least of all that the condition still holds."""
    from zrb.llm.tool import journal_expiry

    target = tmp_path / "growing.py"
    target.write_text("x" * 17, encoding="utf-8")
    monkeypatch.setattr(journal_expiry, "MAX_HASH_BYTES", 16)
    monkeypatch.setattr(
        journal_expiry.os,
        "fstat",
        lambda descriptor: SimpleNamespace(st_mode=stat.S_IFREG, st_size=1),
    )

    assert file_sha(str(target)) == ""


def test_the_read_walks_the_tree_it_validated(tmp_path, monkeypatch):
    """`O_NOFOLLOW` guards the last component only, so a directory swapped for a
    link after validation would still be followed. The walk opens each component
    from its parent's descriptor, so the swap has nothing left to redirect."""
    from zrb.llm.tool import journal_expiry

    root = tmp_path / "repo"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "config.py").write_text("x\n", encoding="utf-8")
    outside = tmp_path / "sensitive"
    outside.mkdir()
    (outside / "config.py").write_text("secret\n", encoding="utf-8")
    (root / "sub").rename(root / "moved")
    try:
        (root / "sub").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("this platform does not allow symlinks without elevation")
    # Stand in for the validation that ran before the swap: it still answers the
    # path it checked, so only the walk stands between the read and the link.
    inside = lambda value, tree: str(root / value)  # noqa: E731
    monkeypatch.setattr(journal_expiry, "condition_path", inside)

    condition = Condition("file", "sub/config.py")

    assert (
        journal_expiry.is_condition_met(
            condition, str(root), "3.29", "zrb", "deadbeefcafe"
        )
        is None
    )


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
    notes = [_note("technical/a.md", "file:settings.py", repo="soda", digest="deadbeefcafe")]

    assert expired_note_rels(notes, str(tmp_path), "zrb", "3.29") == set()


def test_a_proved_file_expires_and_an_unstamped_one_does_not(tmp_path):
    target = tmp_path / "settings.py"
    target.write_text("retries = 1\n", encoding="utf-8")
    digest = condition_digest("file:settings.py", str(tmp_path))
    target.write_text("retries = 3\n", encoding="utf-8")
    notes = [
        _note("technical/changed.md", "file:settings.py", digest=digest),
        _note("technical/unstamped.md", "file:settings.py"),
    ]

    assert expired_note_rels(notes, str(tmp_path), "zrb", "3.29") == {
        "technical/changed.md"
    }


def test_an_expired_notes_line_leaves_the_index_and_a_hand_written_one_stays():
    """Expiry hides what the writer generated, exactly as scoping does: a line a
    person wrote is not the writer's to drop."""
    text = (
        "## Constraints\n\n"
        "- a bank job red at prepare is infra ([note](technical/bank-job.md))\n"
        "- extra context ([note](technical/old-note.md))\n"
    )
    notes = [
        _note("technical/bank-job.md", "version:<3.29"),
        _note("technical/old-note.md", "version:<3.29", hud_line=""),
    ]
    expired = expired_note_rels(notes, "", "zrb", "3.29")

    rendered = scope_index(text, notes, "zrb", expired)

    assert "a bank job red at prepare is infra" not in rendered
    assert "extra context" in rendered
