"""Live-session renaming (rekey) and sub-agent titles (ADR-0109)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.subagent.live_session import (
    LiveSubAgentSessionRegistry,
    start_titling,
)


@pytest.fixture
def registry():
    return LiveSubAgentSessionRegistry()


@pytest.fixture
def buffered_ui():
    ui = MagicMock()
    ui.active_run_context = None
    return ui


@pytest.fixture
def sub_agent_manager():
    return MagicMock()


def test_rekey_keeps_sessions_addressable_under_the_new_name(
    registry, buffered_ui, sub_agent_manager
):
    entry = registry.add_session(
        "old", "a1", "reviewer", sub_agent_manager, buffered_ui
    )

    registry.rekey("old", "new")

    assert registry.get("old", "a1") is None
    assert registry.get("new", "a1") is entry
    assert entry.session_id == "new"
    buffered_ui.set_session_id.assert_called_once_with("new")


def test_rekey_refuses_to_replace_a_session_already_at_the_destination(
    registry, buffered_ui, sub_agent_manager
):
    mine = registry.add_session("old", "a1", "reviewer", sub_agent_manager, buffered_ui)
    other = registry.add_session("new", "a1", "planner", sub_agent_manager, buffered_ui)

    assert registry.can_rekey("old", "new") is False
    with pytest.raises(ValueError):
        registry.rekey("old", "new")

    assert registry.get("old", "a1") is mine
    assert registry.get("new", "a1") is other


@pytest.mark.asyncio
async def test_a_new_title_repaints_the_parent_ui(
    registry, buffered_ui, sub_agent_manager
):
    entry = registry.add_session("s", "a1", "reviewer", sub_agent_manager, buffered_ui)
    with patch(
        "zrb.llm.agent.subagent.live_session.suggest_slug",
        AsyncMock(return_value="fix-login"),
    ):
        start_titling(entry, "fix the login bug")
        await asyncio.sleep(0.05)

    assert entry.title == "fix-login"
    buffered_ui.parent_ui.invalidate_ui.assert_called_once()
