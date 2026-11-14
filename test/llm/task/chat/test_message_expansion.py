"""Tests for llm/task/chat/message_expansion.py."""

from unittest.mock import MagicMock

from zrb.llm.subagent.manager.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.task.chat.message_expansion import (
    expand_message,
    is_action_command,
    resolve_agent_mention,
)


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


def test_an_action_command_is_recognised_and_anything_else_is_not():
    """`/photo` acts on zrb itself, so a session runs it where the UI exists."""
    from zrb.llm.custom_command.action_command import ActionCommand

    photo = ActionCommand("/photo", lambda args, ui: "taken")
    assert is_action_command("/photo", [photo]) is True
    assert is_action_command("/unknown", [photo]) is False
    assert is_action_command("a plain message", [photo]) is False
    assert is_action_command(None, [photo]) is False


def test_a_command_wins_over_a_mention_and_an_unknown_command_reaches_the_mention():
    """The order is the point: the command is the more explicit ask."""
    from unittest.mock import patch

    outcome = MagicMock(prompt="PROMPT", reply="REPLY")
    with (
        patch("zrb.llm.task.chat.message_expansion.run_custom_command") as run,
        patch("zrb.llm.task.chat.message_expansion.resolve_agent_mention") as mention,
    ):
        run.return_value = outcome
        assert expand_message("/cmd hi @researcher", []) == ("PROMPT", "REPLY")
        mention.assert_not_called()

        run.return_value = None
        mention.return_value = "NUDGED"
        assert expand_message("/cmd hi @researcher", []) == ("NUDGED", None)

        mention.return_value = None
        assert expand_message("plain", []) == ("plain", None)
        assert expand_message(None, []) == (None, None)
