"""Tests for llm/app/completion/args.py."""

from unittest.mock import MagicMock

from zrb.llm.app.completion.args import (
    complete_copy_arg,
    complete_exec_arg,
    complete_load_arg,
    complete_redirect_arg,
    complete_save_arg,
)


def test_complete_save_arg_yields_existing_sessions():
    hm = MagicMock()
    hm.search.return_value = ["alpha", "beta"]
    results = list(complete_save_arg("a", hm))
    completions = [c.text for c in results]
    assert "alpha" in completions
    assert "beta" in completions


def test_complete_load_arg_caps_at_ten_results():
    hm = MagicMock()
    hm.search.return_value = [f"sess-{i}" for i in range(25)]
    results = list(complete_load_arg("sess", hm))
    assert len(results) == 10


def test_complete_redirect_arg_silent_when_prefix_doesnt_match_timestamp():
    """If prefix is 'zzz', the timestamp-based suggestion is suppressed."""
    results = list(complete_redirect_arg("zzz"))
    assert results == []


def test_complete_redirect_arg_yields_response_prefixed_timestamp():
    """Empty prefix yields a single response-<timestamp>.txt suggestion."""
    results = list(complete_redirect_arg(""))
    assert len(results) == 1
    assert results[0].text.startswith("response-")
    assert results[0].text.endswith(".txt")


def test_complete_copy_arg_silent_when_prefix_doesnt_match():
    """If prefix is 'zzz', the copy suggestion is suppressed."""
    results = list(complete_copy_arg("zzz"))
    assert results == []


def test_complete_copy_arg_yields_transcript_prefixed_timestamp():
    """Empty prefix yields a single transcript-<timestamp>.txt suggestion."""
    results = list(complete_copy_arg(""))
    assert len(results) == 1
    assert results[0].text.startswith("transcript-")
    assert results[0].text.endswith(".txt")


def test_complete_exec_arg_returns_recent_first():
    cmd_history = ["echo hi", "echo bye", "ls -la"]
    results = list(complete_exec_arg("echo", cmd_history))
    texts = [c.text for c in results]
    # Most recent first → "echo bye" before "echo hi"
    assert texts == ["echo bye", "echo hi"]


def test_complete_exec_arg_filters_by_prefix():
    cmd_history = ["echo hi", "ls -la", "grep foo"]
    results = list(complete_exec_arg("ls", cmd_history))
    assert [c.text for c in results] == ["ls -la"]
