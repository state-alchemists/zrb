"""An edit never leaves a working file broken.

Two ways it used to. A `new_text` that omitted the newline its `old_text`
ended with joined the following line onto the replacement, and that only
surfaced afterwards, as a diagnostic about a file already on disk. A
replacement that produced unparsable Python was likewise written first and
reported second, so the caller had to repair a file it never meant to break.
"""

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.tool.file import replace_in_file
from zrb.llm.tool.file_observation import clear_observed


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
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        yield


def _write_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _read_text(path):
    with open(path, "r", encoding="utf-8") as f:
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
