"""A continued sub-agent session saves its transcript again (ADR-0109)."""

from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.subagent.live_session import LiveSubAgentSessionRegistry


@pytest.mark.asyncio
async def test_a_continuation_saves_the_new_history():
    registry = LiveSubAgentSessionRegistry()
    buffered_ui = MagicMock()
    buffered_ui.active_run_context = None
    entry = registry.add_session("s", "a1", "reviewer", MagicMock(), buffered_ui)
    saved = []
    entry.persist_history = saved.append

    async def fake_run_agent(**kwargs):
        return "ok", [{"turn": 2}]

    with (
        patch(
            "zrb.llm.agent.subagent.live_session.steer_into_live_run",
            return_value=False,
        ),
        patch(
            "zrb.llm.agent.subagent.live_session.run_agent", side_effect=fake_run_agent
        ),
    ):
        await registry.send_message("s", "a1", "and one more thing")
        await entry.active_task

    assert saved == [[{"turn": 2}]]
