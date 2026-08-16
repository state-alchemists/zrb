"""Tests for llm/util/subagent_session_naming.py — the single source of truth
for the delegated sub-agent conversation-name shape (Item 4, Phase A/D)."""

from zrb.llm.util.subagent_session_naming import (
    format_delegated_session_name,
    parse_delegated_session,
)


def test_format_and_parse_round_trip():
    name = format_delegated_session_name("sess1", "researcher", "deadbeef")
    assert name == "sess1-sub-researcher-deadbeef"
    assert parse_delegated_session(name) == ("sess1", "researcher")


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
