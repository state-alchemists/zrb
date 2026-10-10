"""Tools for the main agent and a delegated sub-agent to message each other.

The main agent's side of ADR-0108; the sub-agent's side is
`subagent/parent_message.py`. Delivery reuses the live-session registry: a
message steers into a live turn or queues for the next, and names its sender.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from zrb.llm.ambient_state import (
    get_current_tool_session,
    get_session_ownership_key,
)
from zrb.llm.subagent.live_session import live_subagent_session_registry


def create_send_message_to_subagent_tool():
    async def send_message_to_subagent(
        agent_id: Annotated[
            str, Field(description="The sub-agent's id, as shown in its delegation.")
        ],
        message: Annotated[str, Field(description="What to tell the sub-agent.")],
    ) -> str:
        """Send a message to a delegated sub-agent that is still running or idle.

        The sub-agent sees it as coming from you. Use it to redirect a
        background delegation or answer its question; its reply comes back as
        a message to you, not as this call's result.
        """
        session_id = get_session_ownership_key(get_current_tool_session())
        registry = live_subagent_session_registry
        if not registry.has_message_budget(session_id, agent_id):
            return registry.describe_send_refusal(session_id, agent_id)
        registry.record_agent_message(session_id, agent_id)
        await registry.send_message(
            session_id, agent_id, f"[message from the main agent]\n{message}"
        )
        return f"Message sent to sub-agent {agent_id}."

    setattr(send_message_to_subagent, "zrb_is_delegate_tool", True)
    return send_message_to_subagent
