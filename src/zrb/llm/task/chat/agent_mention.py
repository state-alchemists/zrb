"""Detects `@agent-name` mentions in a chat message and nudges the main agent
to delegate to that agent, mirroring `resolve_custom_command`'s detect-and-
transform shape but for agent routing instead of slash commands.

Deliberately minimal: no new approval-bypass machinery. The nudge only
changes what the main agent is told to prefer — the `DelegateToAgent` call it
makes as a result still goes through the exact same permission/approval gates
as any model-initiated delegation.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from zrb.llm.agent.subagent.manager import (
    sub_agent_manager as default_sub_agent_manager,
)

if TYPE_CHECKING:
    from zrb.llm.agent.subagent.manager import SubAgentManager

_MENTION_PATTERN = re.compile(r"@([\w-]+)")


def resolve_agent_mention(
    message: str,
    sub_agent_manager: "SubAgentManager | None" = None,
) -> str | None:
    """If *message* mentions one or more known sub-agents via `@name`, return
    the message prefixed with a delegation nudge naming them.

    An `@word` that does not match a registered agent is left alone — it may
    be an email address or someone's handle in prose, not an error. Returns
    ``None`` when no known agent is mentioned, so callers can tell "no
    mention" apart from "mentioned, nudge attached".
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
