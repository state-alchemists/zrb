"""Tests for llm/task/chat/agent_mention.py."""

from unittest.mock import MagicMock

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.task.chat.agent_mention import resolve_agent_mention


def _manager_with(*names: str) -> SubAgentManager:
    manager = MagicMock(spec=SubAgentManager)
    definitions = {
        name: SubAgentDefinition(
            name=name, path="path", description="d", system_prompt="p"
        )
        for name in names
    }
    manager.get_agent_definition.side_effect = definitions.get
    return manager


def test_no_mention_returns_none():
    manager = _manager_with("researcher")
    assert resolve_agent_mention("plain message, no mention here", manager) is None


def test_unknown_mention_is_silently_ignored():
    """An `@word` that isn't a registered agent is prose, not an error."""
    manager = _manager_with("researcher")
    assert resolve_agent_mention("email me at foo@example.com", manager) is None


def test_known_mention_prepends_nudge_and_keeps_original_message():
    manager = _manager_with("researcher")
    out = resolve_agent_mention("Please look into this with @researcher", manager)
    assert out is not None
    assert "`researcher`" in out
    assert "DelegateToAgent" in out
    assert "Please look into this with @researcher" in out


def test_multiple_known_mentions_all_appear_in_the_nudge():
    manager = _manager_with("researcher", "code-reviewer")
    out = resolve_agent_mention(
        "Have @researcher dig in, then @code-reviewer check it", manager
    )
    assert out is not None
    assert "`researcher`" in out
    assert "`code-reviewer`" in out


def test_duplicate_mention_listed_once():
    manager = _manager_with("researcher")
    out = resolve_agent_mention("@researcher and again @researcher", manager)
    assert out is not None
    assert out.count("`researcher`") == 1


def test_mixed_known_and_unknown_mentions_only_lists_known():
    """The unknown mention stays untouched in the original message (it's
    prose, not an error), but must not appear in the nudge line itself."""
    manager = _manager_with("researcher")
    out = resolve_agent_mention("ask @researcher, cc @not-an-agent", manager)
    assert out is not None
    nudge, _, original_message = out.partition("\n\n")
    assert "`researcher`" in nudge
    assert "not-an-agent" not in nudge
    assert original_message == "ask @researcher, cc @not-an-agent"


def test_default_manager_used_when_none_passed():
    """No manager passed falls back to the module singleton, not an error."""
    assert resolve_agent_mention("no mentions at all") is None
