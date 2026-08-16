"""Tests for llm/util/subagent_session_naming.py — the single source of truth
for the delegated sub-agent conversation-name shape (Item 4, Phase A/D)."""

import os

from zrb.llm.util.subagent_session_naming import (
    format_delegated_session_name,
    parse_delegated_session,
    subagent_history_directories,
    subagent_only_directories,
)


def test_format_and_parse_round_trip():
    name = format_delegated_session_name("sess1", "researcher", "deadbeef")
    assert name == "sess1-sub-researcher-deadbeef"
    assert parse_delegated_session(name) == ("sess1", "researcher")


def test_empty_parent_session_falls_back_to_default_and_round_trips():
    """An empty parent_session_id must not produce a name the parser can
    never read back — the `parent` group requires at least one char."""
    name = format_delegated_session_name("", "researcher", "deadbeef")
    assert name == "default-sub-researcher-deadbeef"
    assert parse_delegated_session(name) == ("default", "researcher")


def test_blank_parent_session_also_falls_back():
    name = format_delegated_session_name("   ", "researcher", "deadbeef")
    assert name == "default-sub-researcher-deadbeef"


def test_ordinary_name_returns_none():
    assert parse_delegated_session("my-project-chat") is None


def test_hyphenated_agent_name_still_parses():
    """agent names like 'code-reviewer' must not confuse the greedy match."""
    result = parse_delegated_session("my-sess-sub-code-reviewer-0123abcd")
    assert result == ("my-sess", "code-reviewer")


def test_short_id_suffix_does_not_match():
    """The agent_id suffix must be exactly 8 hex chars, matching
    `uuid.uuid4().hex[:8]` — a shorter/longer tail is not this shape."""
    assert parse_delegated_session("sess1-sub-researcher-abc") is None


def test_hyphenated_parent_session_still_parses():
    result = parse_delegated_session("my-parent-session-sub-researcher-deadbeef")
    assert result == ("my-parent-session", "researcher")


def test_subagent_only_directories_excludes_history_root(tmp_path):
    """Unlike `subagent_history_directories`, the root itself — where
    ordinary (non-delegated) sessions live — is never included. A caller
    that deletes files past a retention count (pruning) needs this narrower
    list; a caller that only reads/lists can afford the broader one."""
    (tmp_path / "subagent" / "researcher").mkdir(parents=True)
    (tmp_path / "subagent" / "code-reviewer").mkdir(parents=True)

    only = subagent_only_directories(str(tmp_path))
    assert str(tmp_path) not in only
    assert {os.path.basename(p) for p in only} == {"researcher", "code-reviewer"}

    full = subagent_history_directories(str(tmp_path))
    assert str(tmp_path) in full
    assert set(full) == {str(tmp_path)} | set(only)


def test_subagent_only_directories_missing_subagent_root_returns_empty(tmp_path):
    assert subagent_only_directories(str(tmp_path)) == []
