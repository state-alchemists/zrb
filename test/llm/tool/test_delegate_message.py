from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.subagent.live_session import LiveSubAgentSessionRegistry
from zrb.llm.agent.subagent.parent_message import send_message_to_parent
from zrb.llm.tool.delegate_message import create_send_message_to_subagent_tool
from zrb.llm.ui.buffered_ui import BufferedUI

SESSION = "sess"


@pytest.fixture
def registry():
    reg = LiveSubAgentSessionRegistry()
    with (
        patch("zrb.llm.tool.delegate_message.live_subagent_session_registry", reg),
        patch(
            "zrb.llm.agent.subagent.parent_message.live_subagent_session_registry", reg
        ),
    ):
        yield reg


def _add(registry, parent):
    ui = BufferedUI(parent, session_id=SESSION)
    ui.set_activity_id("abcd1234")
    registry.add_session(SESSION, "abcd1234", "reviewer", MagicMock(), ui)
    return ui


@pytest.mark.asyncio
async def test_sub_agent_message_reaches_parent_with_sender(registry):
    parent = MagicMock()
    ui = _add(registry, parent)
    with patch("zrb.llm.agent.subagent.parent_message.get_current_ui", return_value=ui):
        result = await send_message_to_parent("need the repo path")
    assert "sent" in result
    sent = parent.submit_message.call_args.args[0]
    assert sent.startswith('[message from sub-agent "reviewer" (abcd1234)]')
    assert sent.endswith("need the repo path")


@pytest.mark.asyncio
async def test_parent_message_names_the_main_agent(registry):
    _add(registry, MagicMock())
    tool = create_send_message_to_subagent_tool()
    with (
        patch(
            "zrb.llm.tool.delegate_message.get_session_ownership_key",
            return_value=SESSION,
        ),
        patch.object(registry, "send_message") as send,
    ):
        send.return_value = True
        result = await tool("abcd1234", "use main")
    assert "sent" in result
    assert send.call_args.args[2] == "[message from the main agent]\nuse main"


@pytest.mark.asyncio
async def test_unknown_agent_lists_live_ids(registry):
    _add(registry, MagicMock())
    tool = create_send_message_to_subagent_tool()
    with patch(
        "zrb.llm.tool.delegate_message.get_session_ownership_key",
        return_value=SESSION,
    ):
        result = await tool("nope", "hi")
    assert "SYSTEM SUGGESTION" in result and "abcd1234" in result


@pytest.mark.asyncio
async def test_message_limit_stops_ping_pong(registry, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_AGENT_MESSAGE_LIMIT", "1")
    parent = MagicMock()
    ui = _add(registry, parent)
    with (
        patch("zrb.llm.agent.subagent.parent_message.get_current_ui", return_value=ui),
    ):
        first = await send_message_to_parent("a")
        second = await send_message_to_parent("b")
    assert "sent" in first
    assert "limit" in second
    assert parent.submit_message.call_count == 1


@pytest.mark.asyncio
async def test_outside_a_sub_agent_there_is_no_parent(registry):
    with patch(
        "zrb.llm.agent.subagent.parent_message.get_current_ui", return_value=None
    ):
        assert "not a delegated sub-agent" in await send_message_to_parent("x")
