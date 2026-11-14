"""What a user typed, turned into what the agent sees.

Three shapes share this one entry point, and the order between them is the
point: a slash command runs first because it is the more explicit ask, then an
`@agent` mention, which changes only what the agent is told to prefer.

The mention nudge is a preference, not a grant: the `DelegateToAgent` call it
asks for passes the same permission and approval gates as any other.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.custom_command.resolver import (
    get_custom_command_match,
    run_custom_command,
)
from zrb.llm.subagent.manager.manager import (
    sub_agent_manager as default_sub_agent_manager,
)

if TYPE_CHECKING:
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.subagent.manager.manager import SubAgentManager

_MENTION_PATTERN = re.compile(r"@([\w-]+)")


def is_action_command(
    message: str | None, custom_commands: "list[AnyCustomCommand]"
) -> bool:
    """Whether *message* is a slash command that answers without a turn.

    An `ActionCommand` acts on zrb itself (`/photo`, `/model`) and may need the
    UI, so a session runs it where the UI exists rather than through a turn.
    """
    if not isinstance(message, str):
        return False
    match = get_custom_command_match(message, custom_commands)
    return match is not None and isinstance(match[0], ActionCommand)


def expand_message(
    message: str | None, custom_commands: "list[AnyCustomCommand]"
) -> tuple[str | None, str | None]:
    """Expand a slash command, else an @agent mention, in a string message.

    Returns ``(message, reply)``; an `ActionCommand` handled in-process returns
    ``(None, reply)`` since there is no turn to run.
    """
    if not isinstance(message, str):
        return message, None
    outcome = run_custom_command(message, custom_commands, None)
    if outcome is not None:
        return outcome.prompt, outcome.reply
    mentioned = resolve_agent_mention(message)
    return (message if mentioned is None else mentioned), None


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
