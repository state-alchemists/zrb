from unittest.mock import MagicMock, patch

import pytest

from zrb.task.llm.file_replacement import (
    FileReplacement,
    _expand_context_for_uniqueness,
    _expand_to_word_boundary,
    _generate_optimized_replacements,
    edit_replacement,
    is_single_path_replacement,
)


def test_is_single_path_replacement():
    # Valid dict
    assert is_single_path_replacement({"path": "p", "old_text": "o", "new_text": "n"})
    assert is_single_path_replacement(
        {"path": "p", "old_text": "o", "new_text": "n", "count": 1}
    )

    # Invalid dict
    assert not is_single_path_replacement({"path": "p"})  # missing keys
    assert not is_single_path_replacement({"path": "p", "extra": "e"})  # keys mismatch

    # Valid list
    assert is_single_path_replacement(
        [
            {"path": "p", "old_text": "o1", "new_text": "n1"},
            {"path": "p", "old_text": "o2", "new_text": "n2"},
        ]
    )

    # Invalid list (different paths)
    assert not is_single_path_replacement(
        [
            {"path": "p1", "old_text": "o", "new_text": "n"},
            {"path": "p2", "old_text": "o", "new_text": "n"},
        ]
    )

    # Not dict or list
    assert not is_single_path_replacement("string")


@patch("zrb.task.llm.file_replacement.read_file")
@patch("zrb.task.llm.file_replacement._open_diff_editor")
def test_edit_replacement_no_change(mock_open_editor, mock_read_file):
    # Setup
    original_text = "Hello World"
    replacement = {"path": "file.txt", "old_text": "World", "new_text": "Universe"}
    mock_read_file.return_value = original_text

    # User saves file exactly as proposed
    mock_open_editor.return_value = "Hello Universe"

    result, changed = edit_replacement(replacement)

    assert not changed
    assert result == replacement
    mock_open_editor.assert_called_once()


@patch("zrb.task.llm.file_replacement.read_file")
@patch("zrb.task.llm.file_replacement._open_diff_editor")
def test_edit_replacement_with_change(mock_open_editor, mock_read_file):
    # Setup
    original_text = "Hello World"
    # Proposal: Change "World" to "Universe"
    replacement = {"path": "file.txt", "old_text": "World", "new_text": "Universe"}
    mock_read_file.return_value = original_text

    # User changes it to "Hello Galaxy" instead
    mock_open_editor.return_value = "Hello Galaxy"

    result, changed = edit_replacement(replacement)

    assert changed
    # Logic should detect that "World" -> "Galaxy"
    # result is a list of replacements.
    assert len(result) == 1
    assert result[0]["old_text"] == "World"
    assert result[0]["new_text"] == "Galaxy"


def test_generate_optimized_replacements_simple():
    path = "test.py"
    original = "def foo():\n    print('bar')\n"
    edited = "def foo():\n    print('baz')\n"

    replacements = _generate_optimized_replacements(path, original, edited)

    assert len(replacements) == 1
    r = replacements[0]
    # Ideally it replaces 'bar' with 'baz'
    assert "bar" in r["old_text"]
    assert "baz" in r["new_text"]
    assert r["path"] == path


def test_generate_optimized_replacements_multiple():
    path = "test.txt"
    original = "Line 1\nLine 2\nLine 3"
    edited = "Line 1A\nLine 2\nLine 3B"

    replacements = _generate_optimized_replacements(path, original, edited)

    # Should detect two separate changes if lines are far apart (context threshold)
    # But here lines are close.
    # Check logic merge_threshold=200 in code.
    # Lines are very close, so it might merge them into one big replacement "Line 1\nLine 2\nLine 3" -> "Line 1A\nLine 2\nLine 3B"

    # Let's test checking the output directly
    assert len(replacements) > 0
    # Just ensure the transformation is equivalent
    res = original
    for r in replacements:
        res = res.replace(r["old_text"], r["new_text"], 1)
    assert res == edited


def test_expand_context_for_uniqueness():
    content = "foo bar foo baz"
    # First 'foo' is at 0:3
    # Second 'foo' is at 8:11

    # Expand first foo
    s, e = _expand_context_for_uniqueness(content, 0, 3)
    # 'foo' is not unique (count=2).
    # 'foo ' (0:4) might be unique? "foo " appears at 0:4 and "foo " at 8:12. Wait "foo baz"
    # "foo b" vs "foo ba"

    # Just verifies it expands.
    assert s <= 0
    assert e >= 3
    assert content.count(content[s:e]) == 1


def test_expand_to_word_boundary():
    content = "hello world"
    # Range inside "hello": 1:4 "ell"
    s, e = _expand_to_word_boundary(content, 1, 4)
    # Should expand to "hello" (0:5)
    assert s == 0
    assert e == 5
    assert content[s:e] == "hello"


@patch("subprocess.call")
@patch("zrb.task.llm.file_replacement.read_file")
def test_open_diff_editor(mock_read, mock_call):
    from zrb.task.llm.file_replacement import _open_diff_editor

    mock_read.return_value = "edited content"

    res = _open_diff_editor("path.txt", "orig", "prop", "vimdiff {old} {new}")

    assert res == "edited content"
    mock_call.assert_called_once()
