"""Sub-agent session titles (ADR-0109)."""

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
