"""Persona-swap-on-`/load` state for `BaseUI`; the logic is in
`conversation_commands.py`."""

from __future__ import annotations

from typing import Any


class BaseUIPersonaState:
    """None until a delegated sub-agent session is loaded via `/load`."""

    def __init__(self) -> None:
        self.active_subagent: str | None = None
        self.original_snapshot: "dict[str, Any] | None" = None
