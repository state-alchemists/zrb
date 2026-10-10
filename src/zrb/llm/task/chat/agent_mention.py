"""Detects `@agent-name` mentions in a chat message and nudges the main agent
to delegate to that agent, like `resolve_custom_command` does for slash commands.

The nudge only changes what the agent is told to prefer; the resulting
`DelegateToAgent` call passes the same permission/approval gates as any other.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from zrb.llm.subagent.manager import sub_agent_manager as default_sub_agent_manager

if TYPE_CHECKING:
    from zrb.llm.subagent.manager import SubAgentManager

_MENTION_PATTERN = re.compile(r"@([\w-]+)")


def resolve_agent_mention(
    message: str,
    sub_agent_manager: "SubAgentManager | None" = None,
) -> str | None:
    """Prefix *message* with a delegation nudge naming the sub-agents it `@mentions`.

    Unknown `@words` (emails, handles) are ignored. Returns ``None`` when no
    known agent is mentioned.
    """
    if sub_agent_manager is None:
        sub_agent_manager = default_sub_agent_manager

    names: list[str] = []
    for match in _MENTION_PATTERN.finditer(message):
        candidate = match.group(1)
        if candidate in names:
            continue
        if sub_agent_manager.get_agent_definition(candidate):
            names.append(candidate)

    if not names:
        return None

    mentioned = ", ".join(f"`{name}`" for name in names)
    nudge = (
        f"[User explicitly requested delegation to: {mentioned}. Prefer "
        "DelegateToAgent for this request unless it is clearly not applicable.]"
    )
    return f"{nudge}\n\n{message}"
