"""Sub-agent session titles (ADR-0109)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.subagent.live_session import (
    LiveSubAgentSessionRegistry,
    start_titling,
)


@pytest.fixture(autouse=True)
def _auto_naming_on(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_AUTO_NAME_ENABLED", "on")


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


async def _title(registry, entry, answer="fix-login"):
    with (
        patch(
            "zrb.llm.subagent.live_session.live_subagent_session_registry",
            registry,
        ),
        patch(
            "zrb.llm.subagent.live_session.suggest_slug",
            AsyncMock(return_value=answer),
        ),
    ):
        start_titling(entry, "fix the login bug")
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_a_new_title_repaints_the_parent_ui(
    registry, buffered_ui, sub_agent_manager
):
    entry = registry.add_session("s", "a1", "reviewer", sub_agent_manager, buffered_ui)

    await _title(registry, entry)

    assert entry.title == "fix-login"
    buffered_ui.parent_ui.invalidate_ui.assert_called_once()


@pytest.mark.asyncio
async def test_a_title_for_a_cleared_session_is_dropped(
    registry, buffered_ui, sub_agent_manager
):
    entry = registry.add_session("s", "a1", "reviewer", sub_agent_manager, buffered_ui)
    registry.clear("s")

    await _title(registry, entry)

    assert entry.title == ""
    buffered_ui.parent_ui.invalidate_ui.assert_not_called()
