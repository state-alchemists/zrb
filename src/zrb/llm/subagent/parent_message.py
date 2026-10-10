"""The sub-agent's side of ADR-0108: a tool to message the main agent.

Lives in the sub-agent package, beside the registry it reads, so
`building.py` can attach it without a cycle through `zrb.llm.tool`. The main
agent's side is `tool/delegate_message.py`.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from zrb.llm.agent_state import get_current_ui
from zrb.llm.permission import Capability, tag
from zrb.llm.subagent.live_session import live_subagent_session_registry
from zrb.llm.ui.buffered_ui import BufferedUI


async def send_message_to_parent(
    message: Annotated[str, Field(description="What to tell the main agent.")],
) -> str:
    """Send a message to the main agent that delegated this task, without ending.

    Use it for a question you cannot proceed without or a progress note worth
    interrupting for. The main agent sees it as coming from you.
    """
    ui = get_current_ui()
    agent_id = ui.agent_id if isinstance(ui, BufferedUI) else None
    if not isinstance(ui, BufferedUI) or agent_id is None:
        return "[SYSTEM SUGGESTION] You are not a delegated sub-agent; there is no parent to message."
    registry = live_subagent_session_registry
    entry = registry.get(ui.session_id, agent_id)
    if entry is None or not registry.has_message_budget(ui.session_id, agent_id):
        return registry.describe_send_refusal(ui.session_id, agent_id)
    parent = registry.get_parent_ui(ui.session_id, agent_id)
    if parent is None:
        return "[SYSTEM SUGGESTION] The main agent cannot receive messages right now; finish and report in your final answer."
    registry.record_agent_message(ui.session_id, agent_id)
    header = f'[message from sub-agent "{entry.agent_name}" ({agent_id})]'
    parent.submit_message(f"{header}\n{message}")
    return "Message sent to the main agent."


tag(send_message_to_parent, Capability.META)
