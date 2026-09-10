"""Persona-swap-on-`/load` state for `BaseUI`.

Self-contained like `BaseUIUsage`: the swap/restore logic lives entirely in
`BaseUIConversationCommands` (`llm/ui/base/conversation_commands.py`), which
reaches this state only through `BaseUI`'s public properties
(`active_subagent_persona`, `original_persona_snapshot`) — so this part needs
no reference back to the owner.
"""

from __future__ import annotations

from typing import Any


class BaseUIPersonaState:
    """None until a delegated sub-agent session is loaded via `/load`."""

    def __init__(self) -> None:
        self.active_subagent: str | None = None
        self.original_snapshot: "dict[str, Any] | None" = None
