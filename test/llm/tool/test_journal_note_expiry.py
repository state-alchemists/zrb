"""A note's expiry: the condition it holds under, and how it is retired.

A finding used to have a birth and no end — its Context was written once and
never re-read — so a disproved claim stayed in every turn's context until
somebody noticed. The frontmatter now says when the finding stops applying, and
`SupersedeJournalNote` retires it while keeping the evidence.
"""

import os
from unittest.mock import patch

import pytest

from zrb.llm.tool.journal_expiry import checkout_id, file_sha


@pytest.fixture
def writable_journal(tmp_path):
    """Patch CFG for the writer module and return the journal root."""
    root = tmp_path / "notes"
    with patch("zrb.llm.tool.journal_write.CFG") as mock_cfg, patch(
        "zrb.llm.tool.journal_write.repo_of", return_value="zrb"
    ):
        mock_cfg.LLM_JOURNAL_DIR = str(root)
        mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
        mock_cfg.LLM_JOURNAL_LOCK_TIMEOUT = 0.1
        mock_cfg.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION = 20
        mock_cfg.LLM_JOURNAL_CATALOG_MAX_ENTRIES = 25
        # Off here so these tests stay fast and independent of a `git` binary —
        # test_journal_git.py exercises git-backing.
        mock_cfg.LLM_JOURNAL_GIT_ENABLED = False
        yield str(root)


def _write(slug: str, applies_when: str) -> str:
    from zrb.llm.tool.journal_write import write_journal_note

    return write_journal_note(
        category="technical",
        slug=slug,
        title="A title",
        context="When it applies.",
        finding="The finding.",
        source="src/zrb/llm/tool/journal_note.py:52",
        hud_line="the claim itself",
        applies_when=applies_when,
    )


def _read(*parts) -> str:
    with open(os.path.join(*parts), "r", encoding="utf-8") as f:
        return f.read()


def test_a_note_says_when_it_stops_applying(writable_journal):
    """The condition is what makes a note retirable: a finding nobody wrote the
    expiry of can only be re-read, never checked."""
    from zrb.llm.tool.journal_write import write_journal_note

    write_journal_note(
        category="technical",
        slug="prebuffer",
        title="The cushion is a setting",
        context="While zrb ships the pocket engine",
        finding="A sentence starts on a cushion of audio",
        hud_line="A sentence starts on a cushion of audio",
        source="pcm_player.py:1",
        applies_when="while pocket stays the default speech engine",
    )

    note = _read(writable_journal, "technical/prebuffer.md")
    assert "applies_when: while pocket stays the default speech engine" in note
    assert "status: active" in note


def test_a_note_that_does_not_say_why_it_would_stop_is_refused(writable_journal):
    """The condition stopped being optional: a finding nobody wrote the expiry of
    can only be re-read, and 111 notes saying `not stated` is what that costs."""
    from zrb.llm.tool.journal_write import write_journal_note

    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="technical",
            slug="vague",
            title="T",
            context="c",
            finding="f",
            hud_line="f",
            source="s",
        )

    assert str(excinfo.value).startswith("[SYSTEM SUGGESTION]")
    assert "a later session can check" in str(excinfo.value)
    assert not os.path.isfile(os.path.join(writable_journal, "technical/vague.md"))


def test_the_placeholder_an_old_writer_stored_is_not_a_condition(writable_journal):
    """`not stated` is read — an older note carrying it still loads — but writing
    it back is refused, so the placeholder cannot spread to a new note."""
    from zrb.llm.tool.journal_write import write_journal_note

    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="technical",
            slug="vague",
            title="T",
            context="c",
            finding="f",
            hud_line="f",
            source="s",
            applies_when="not stated",
        )

    assert "placeholder" in str(excinfo.value)
    assert not os.path.isfile(os.path.join(writable_journal, "technical/vague.md"))


def test_superseding_takes_the_line_out_of_the_index_and_keeps_the_file(
    writable_journal,
):
    """A note that stopped applying costs every turn it stays in the index; its
    evidence is what keeps the journal able to explain itself."""
    from zrb.llm.tool.journal_write import (
        supersede_journal_note,
        write_journal_note,
    )

    write_journal_note(
        category="technical",
        slug="old-cause",
        title="Stutter comes from GIL contention",
        context="c",
        finding="f",
        source="s",
        hud_line="Stutter comes from GIL contention.",
        applies_when="until the decode timings are measured",
    )
    assert "Stutter comes from GIL contention." in _read(writable_journal, "index.md")

    result = supersede_journal_note(
        "technical", "old-cause", "superseded by the prebuffer note: it was a cushion"
    )

    index = _read(writable_journal, "index.md")
    assert "Stutter comes from GIL contention." not in index
    # The root index is what is injected, so nothing of the note stays in it;
    # the category index keeps the link, because the note still exists.
    assert "old-cause" not in index
    assert "old-cause" in _read(writable_journal, "technical/index.md")
    note = _read(writable_journal, "technical/old-cause.md")
    assert "status: superseded" in note
    assert "superseded by the prebuffer note: it was a cushion" in note
    assert "Removed from the index" in result


def test_a_slug_that_climbs_out_of_its_category_is_refused(writable_journal):
    """A slug is free text interpolated into a path, so `../index` is not a note
    name — joining it lands on the root index and the tool would write frontmatter
    into a file it never meant to touch."""
    from zrb.llm.tool.journal_write import (
        delete_journal_note,
        supersede_journal_note,
        write_journal_note,
    )

    write_journal_note(
        "technical",
        "real-note",
        "T",
        "c",
        "f",
        "s",
        applies_when="while zrb 3.29 is released",
        hud_line="f",
    )
    index = _read(writable_journal, "index.md")

    for call in (
        lambda: supersede_journal_note("technical", "../index", "retired"),
        lambda: delete_journal_note("technical", "../index"),
    ):
        with pytest.raises(ValueError, match="kebab-case"):
            call()

    assert _read(writable_journal, "index.md") == index


def test_the_journal_tools_are_reachable_from_the_package(writable_journal):
    """The lazy package is the public API for a Python caller; a tool registered
    for the model but missing here is an ImportError away from unusable."""
    from zrb.llm.tool import delete_journal_note, supersede_journal_note

    assert callable(supersede_journal_note)
    assert callable(delete_journal_note)


def test_a_note_written_here_records_the_digest_of_its_file(writable_journal, tmp_path):
    """In the note's own tree the digest is exactly what makes the condition
    checkable later, and it is stored beside the condition, never inside it."""
    tree = tmp_path / "zrb"
    tree.mkdir()
    (tree / "config.yml").write_text("mode = prod\n", encoding="utf-8")

    with patch("zrb.llm.tool.journal_write.repo_root", return_value=str(tree)):
        _write("build-cache", "file:config.yml")

    body = _read(writable_journal, "technical/build-cache.md")
    assert "applies_when: file:config.yml" in body.splitlines()
    assert f"applies_when_digest: {file_sha(str(tree / 'config.yml'))}" in body
    # The tag is only a directory name; the tree is what the digest is about.
    assert f"applies_when_checkout: {checkout_id(str(tree))}" in body


def test_a_note_from_another_checkout_is_not_re_stamped_here(writable_journal, tmp_path):
    """The tag is a directory name, so two checkouts can share it.

    A revision that changes the condition records the tree it is written in —
    unless the note already names a checkout and this is not it. A digest taken
    here would be compared there, and a mismatch reads as a disproved condition
    about somebody else's file. Unstamped is uncheckable, which keeps the note.
    """
    first = tmp_path / "a" / "zrb"
    first.mkdir(parents=True)
    second = tmp_path / "b" / "zrb"
    second.mkdir(parents=True)
    (first / "a.txt").write_text("A\n", encoding="utf-8")
    (second / "b.txt").write_text("B\n", encoding="utf-8")

    with patch("zrb.llm.tool.journal_write.repo_root", return_value=str(first)):
        _write("build-cache", "file:a.txt")
    assert "applies_when_digest:" in _read(
        writable_journal, "technical/build-cache.md"
    )

    with patch("zrb.llm.tool.journal_write.repo_root", return_value=str(second)):
        _write("build-cache", "file:b.txt")

    body = _read(writable_journal, "technical/build-cache.md")
    assert "applies_when: file:b.txt" in body.splitlines()
    assert "applies_when_digest:" not in body
    assert "applies_when_checkout:" not in body


def test_a_path_with_repeated_spaces_is_stored_and_stamped_as_written(
    writable_journal, tmp_path
):
    """`check_applies_when` folds a sentence onto one line; a path is not a
    sentence. Two spaces in a filename are part of the name the digest is of, and
    folding them would store a condition about a file that does not exist."""
    tree = tmp_path / "zrb"
    tree.mkdir()
    name = "config  prod.yml"
    (tree / name).write_text("mode = prod\n", encoding="utf-8")

    with patch("zrb.llm.tool.journal_write.repo_root", return_value=str(tree)):
        _write("build-cache", f"file:{name}")

    body = _read(writable_journal, "technical/build-cache.md")
    assert f"applies_when: file:{name}" in body
    assert f"applies_when_digest: {file_sha(str(tree / name))}" in body


def test_a_condition_with_a_control_character_is_refused(writable_journal):
    """A NUL makes the path APIs raise rather than answering, so a condition that
    carries one would take the whole write down with it. It is refused, and the
    note is left unwritten — a control character is a corrupted condition, not an
    uncheckable one."""
    from zrb.llm.tool.journal_write import write_journal_note

    with pytest.raises(ValueError) as excinfo:
        write_journal_note(
            category="technical",
            slug="config-x",
            title="T",
            context="c",
            finding="f",
            hud_line="f",
            source="s",
            applies_when="file:src/config.py\x00x",
        )

    assert "control character" in str(excinfo.value)
    assert not os.path.isfile(os.path.join(writable_journal, "technical/config-x.md"))


def test_a_revision_keeps_the_digest_the_note_was_written_with(
    writable_journal, tmp_path
):
    """A digest is evidence. The file changing after the note was written must not
    turn a revision into a fresh hash of the new content — that would renew a
    condition which had stopped holding."""
    tree = tmp_path / "zrb"
    tree.mkdir()
    config = tree / "config.yml"
    config.write_text("mode = prod\n", encoding="utf-8")
    with patch("zrb.llm.tool.journal_write.repo_root", return_value=str(tree)):
        _write("build-cache", "file:config.yml")
    written = file_sha(str(config))
    config.write_text("mode = dev\n", encoding="utf-8")

    with patch("zrb.llm.tool.journal_write.repo_root", return_value=str(tree)):
        _write("build-cache", "file:config.yml")

    assert f"applies_when_digest: {written}" in _read(
        writable_journal, "technical/build-cache.md"
    )


def test_a_revision_records_a_digest_the_note_never_had(writable_journal, tmp_path):
    """Nothing to preserve is not evidence to preserve. A note written while the
    file was missing must become checkable when a revision restates it with the
    file in hand, or it stays uncheckable for good."""
    tree = tmp_path / "zrb"
    tree.mkdir()
    with patch("zrb.llm.tool.journal_write.repo_root", return_value=str(tree)):
        _write("build-cache", "file:config.yml")
    assert "applies_when_digest:" not in _read(
        writable_journal, "technical/build-cache.md"
    )
    (tree / "config.yml").write_text("mode = prod\n", encoding="utf-8")

    with patch("zrb.llm.tool.journal_write.repo_root", return_value=str(tree)):
        _write("build-cache", "file:config.yml")

    assert f"applies_when_digest: {file_sha(str(tree / 'config.yml'))}" in _read(
        writable_journal, "technical/build-cache.md"
    )


def test_a_revision_that_names_another_file_records_that_file(
    writable_journal, tmp_path
):
    """Preserving the old digest is about the *same* condition. A note that now
    points at another file is a different claim, and the digest has to follow it."""
    tree = tmp_path / "zrb"
    tree.mkdir()
    (tree / "config.yml").write_text("mode = prod\n", encoding="utf-8")
    (tree / "other.yml").write_text("mode = test\n", encoding="utf-8")
    with patch("zrb.llm.tool.journal_write.repo_root", return_value=str(tree)):
        _write("build-cache", "file:config.yml")
        _write("build-cache", "file:other.yml")

    assert f"applies_when_digest: {file_sha(str(tree / 'other.yml'))}" in _read(
        writable_journal, "technical/build-cache.md"
    )
