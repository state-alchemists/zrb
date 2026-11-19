"""The narrow UI contract for handing a message to a UI.

A delegated sub-agent reports to the agent that started it through the parent
UI's input side (ADR-0108); the main agent's own side is
`tool/delegate_message.py`. Nothing on that path needs the UI itself — it does
not run it, read its display or drive its picker — so the registry in
`subagent/` types the parent as this, and the runtime check that decides
"is there a parent to message" asks the same question.

It is a `Protocol` rather than an `ABC` because that check is structural: the
question is whether a parent declares an input side, not which class it was
built from. `AnyUI` satisfies it without inheriting it, as it does for
`AnyAgentOutput`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from zrb.llm.contracts.ui.any_ui_input import AnyUIInput


@runtime_checkable
class AnyUIMessageSink(Protocol):
    """Something a message can be handed to. `AnyUI` satisfies this."""

    @property
    def input(self) -> AnyUIInput:
        """The questions this UI can ask, and the queue a message enters."""
        ...
