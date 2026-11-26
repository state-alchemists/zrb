"""An edit never leaves a working file broken.

Two ways it used to. A `new_text` that omitted the newline its `old_text`
ended with joined the following line onto the replacement, and that only
surfaced afterwards, as a diagnostic about a file already on disk. A
replacement that produced unparsable Python was likewise written first and
reported second, so the caller had to repair a file it never meant to break.

A third: the file was read and written with universal-newline translation, so
on POSIX a one-line edit of a CRLF file put every one of its line endings back
as LF. The caller asked for one line and the diff was the whole file.
"""

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.capabilities.tool.file import replace_in_file, write_file
from zrb.llm.capabilities.tool.file.observation import clear_observed


def _r(*a, **kw):
    return asyncio.run(replace_in_file(*a, **kw))


@pytest.fixture(autouse=True)
def _reset_observed_state():
    clear_observed()
    yield
    clear_observed()


@pytest.fixture(autouse=True)
def _no_real_lsp_server():
    """Driving the coroutine through a throwaway loop would leak a server."""
    with patch(
        "zrb.llm.capabilities.tool.file.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        yield


def _write_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def test_an_edit_that_drops_the_trailing_newline_keeps_the_next_line(tmp_path):
    """The replacement has no newline; the line after it must still start its
    own line rather than being glued onto the end of `new_text`."""
    path = os.path.join(tmp_path, "code.py")
    _write_text(path, "first = 1\nsecond = 2\n")

    _r(path, old_text="first = 1\n", new_text="first = 100")

    assert _read_text(path) == "first = 100\nsecond = 2\n"


def test_the_result_says_the_line_break_was_kept(tmp_path):
    """A repair the caller did not ask for must be visible, not silent."""
    path = os.path.join(tmp_path, "code.py")
    _write_text(path, "first = 1\nsecond = 2\n")

    result = _r(path, old_text="first = 1\n", new_text="first = 100")

    assert "line break was kept" in result


def test_every_replaced_occurrence_keeps_its_line_break(tmp_path):
    path = os.path.join(tmp_path, "notes.md")
    _write_text(path, "old\nkeep\nold\n")

    _r(path, old_text="old\n", new_text="new")

    assert _read_text(path) == "new\nkeep\nnew\n"


def test_an_edit_that_would_not_parse_is_refused(tmp_path):
    path = os.path.join(tmp_path, "code.py")
    _write_text(path, "def f():\n    return 1\n")

    result = _r(path, old_text="    return 1", new_text="    return (1")

    assert "was not applied" in result
    assert _read_text(path) == "def f():\n    return 1\n"


def test_a_refused_edit_names_the_syntax_error(tmp_path):
    path = os.path.join(tmp_path, "code.py")
    _write_text(path, "def f():\n    return 1\n")

    result = _r(path, old_text="    return 1", new_text="    return (1")

    assert "SyntaxError" in result


def test_an_edit_to_an_already_broken_file_is_still_applied(tmp_path):
    """Refusing would trap a caller who is fixing the breakage."""
    path = os.path.join(tmp_path, "code.py")
    _write_text(path, "def f(:\n")

    result = _r(path, old_text="def f(:", new_text="def f():")

    assert "Successfully updated" in result
    assert _read_text(path) == "def f():\n"


def test_a_valid_edit_is_applied_unchanged(tmp_path):
    path = os.path.join(tmp_path, "code.py")
    _write_text(path, "def f():\n    return 1\n")

    result = _r(path, old_text="    return 1\n", new_text="    return 2\n")

    assert "Successfully updated" in result
    assert _read_text(path) == "def f():\n    return 2\n"


def test_a_one_line_edit_of_a_crlf_file_keeps_the_other_line_endings(tmp_path):
    """Every byte outside the replaced text comes back as it was read.

    Read and Write both translated line endings: on POSIX the edit put every
    line of the file back as LF, so the diff covered lines it never touched.
    """
    path = os.path.join(tmp_path, "crlf.txt")
    _write_bytes(path, b"first\r\nsecond\r\nthird\r\n")

    _r(path, old_text="second\r\n", new_text="SECOND\r\n")

    assert _read_bytes(path) == b"first\r\nSECOND\r\nthird\r\n"


def test_a_crlf_line_break_is_kept_as_crlf(tmp_path):
    """The `\\r\\n` half of `_keep_line_break` could not run while the read
    translated every ending to `\\n`; restoring a break as LF would still have
    rewritten the line's bytes."""
    path = os.path.join(tmp_path, "crlf.txt")
    _write_bytes(path, b"first\r\nsecond\r\n")

    _r(path, old_text="second\r\n", new_text="SECOND")

    assert _read_bytes(path) == b"first\r\nSECOND\r\n"


def test_a_snippet_copied_from_read_still_matches_a_crlf_file(tmp_path):
    """Read shows a CRLF file's lines with `\\n`, so the snippet a model copies
    carries no `\\r`; it has to be found in the file the edit holds, and the
    file's own ending has to be what the replacement is written with."""
    path = os.path.join(tmp_path, "crlf.txt")
    _write_bytes(path, b"first\r\nsecond\r\nthird\r\n")

    result = _r(path, old_text="second\n", new_text="SECOND\n")

    assert "Successfully updated" in result
    # Not `first\r\nSECOND\nthird\r\n`: a replacement copied from Read carries
    # `\n`, and writing it unchanged mixed two endings in a file that had one.
    assert _read_bytes(path) == b"first\r\nSECOND\r\nthird\r\n"


def test_a_cr_file_is_not_given_mixed_endings_by_a_copied_snippet(tmp_path):
    """The same for a lone-CR file: a copied `\\n` must not land in it."""
    path = os.path.join(tmp_path, "classic.txt")
    _write_bytes(path, b"first\rsecond\r")

    _r(path, old_text="second\n", new_text="SECOND\n")

    assert _read_bytes(path) == b"first\rSECOND\r"


def test_a_cr_line_break_is_kept_as_cr(tmp_path):
    """A legacy Mac file's lines end in a bare `\\r`, and the edit keeps it.

    The break was chosen as `"\\r\\n"` or `"\\n"` only, so a `\\r` matched text
    got no break back: the edit either rewrote the ending or dropped it.
    """
    path = os.path.join(tmp_path, "classic.txt")
    _write_bytes(path, b"first\rsecond\rthird\r")

    _r(path, old_text="second\r", new_text="SECOND")

    assert _read_bytes(path) == b"first\rSECOND\rthird\r"


def test_a_snippet_copied_from_read_does_not_join_the_next_line_in_a_cr_file(
    tmp_path,
):
    """Read shows a `\\r` file's lines with `\\n`, so the copied snippet has no
    break; the replacement must not be glued onto the following line."""
    path = os.path.join(tmp_path, "classic.txt")
    _write_bytes(path, b"first\rsecond\rthird\r")

    _r(path, old_text="second\n", new_text="SECOND")

    assert _read_bytes(path) == b"first\rSECOND\rthird\r"


def test_an_already_applied_edit_is_recognised_across_a_crlf_line_ending(tmp_path):
    """The region already reads as `new_text` once the line ending is counted.

    On Windows every text file on disk carries `\\r\\n`, so a model's `\\n` never
    matches byte for byte and the "already applied" answer never fired there —
    the edit rewrote the file and announced a change it did not make.
    """
    path = os.path.join(tmp_path, "crlf.txt")
    _write_bytes(path, b"foo bar\r\n")

    result = _r(path, old_text="foo bar ", new_text="foo bar\n")

    assert "already applied" in result
    assert _read_bytes(path) == b"foo bar\r\n"


def test_an_edited_crlf_file_is_still_what_this_run_observed(tmp_path):
    """The observation store keys on universal-newline content while the edit
    now holds the file's bytes; recording the bytes would make the next Write
    report a file that changed under it."""
    path = os.path.join(tmp_path, "crlf.txt")
    _write_bytes(path, b"first\r\nsecond\r\n")

    _r(path, old_text="second\r\n", new_text="SECOND\r\n")
    result = asyncio.run(write_file(path, "replaced\n"))

    assert "has changed since it was last read" not in result
