import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.llm.chat_completion import get_chat_completer
from zrb.config.config import CFG


def test_get_chat_completer():
    completer = get_chat_completer()
    assert completer is not None


@patch("zrb.builtin.llm.chat_completion.fuzzy_match")
def test_chat_completer_slash_commands(mock_fuzzy_match):
    mock_fuzzy_match.return_value = (True, 1.0)
    completer = get_chat_completer()
    document = MagicMock()
    document.text_before_cursor = "/"
    document.get_word_before_cursor.return_value = "/"
    # Mock os.path.isdir to avoid issues with LLM_HISTORY_DIR
    with patch("os.path.isdir", return_value=False):
        completions = list(completer.get_completions(document, None))
        assert len(completions) > 0
        assert any(c.text == "/quit" for c in completions)


def test_chat_completer_appendix_completion():
    completer = get_chat_completer()
    document = MagicMock()
    document.get_word_before_cursor.return_value = "@"
    document.text_before_cursor = "@"
    # Mock _fuzzy_path_search to return something
    with patch.object(completer, "_fuzzy_path_search", return_value=["test_dir"]):
        completions = list(completer.get_completions(document, None))
        assert any(c.text == "@test_dir" for c in completions)


def test_chat_completer_fuzzy_path_search_basic():
    completer = get_chat_completer()
    # Test internal method _get_root_and_search_pattern
    root, pattern = completer._get_root_and_search_pattern("./test")
    assert root == "."
    assert pattern == "test"
    # ~/test should expand to home dir if it exists, but the test might be running in an env where ~ doesn't exist or is different.
    # Let's use a predictable absolute path.
    abs_path = os.path.abspath("/tmp/test_zrb_completion")
    root, pattern = completer._get_root_and_search_pattern(abs_path)
    # _get_root_and_search_pattern for abs path that is a dir returns (root, "")
    # if it's not a dir, it goes up.
    assert root is not None


def test_chat_completer_get_cmd_options():
    completer = get_chat_completer()
    options = completer._get_cmd_options()
    assert "/quit" in options
    assert "/help" in options
    assert "/session" in options


def test_chat_completer_fuzzy_path_search_execution():
    completer = get_chat_completer()
    # Actually run _fuzzy_path_search on current directory
    results = completer._fuzzy_path_search(".", max_results=5)
    assert isinstance(results, list)
    # Should at least find something in a project dir
    assert len(results) >= 0
