"""The narrow UI contract that non-UI code is allowed to depend on.

`zrb.llm.tool_call` types its UI parameters as this instead of `AnyUI`, so
pyright rejects reaching past the writer and the input role. Size capped by
`test/architecture/test_agent_output_surface.py`.
"""

from __future__ import annotations

from typing import Protocol, TextIO, runtime_checkable

from zrb.llm.ui.any_ui_input import AnyUIInput


@runtime_checkable
class AnyAgentOutput(Protocol):
    """What tool-call plumbing may ask of a UI. `AnyUI` satisfies this."""

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ) -> None:
        """Write output the way `print()` would, kept for later replay."""
        ...

    @property
    def input(self) -> AnyUIInput:
        """The questions this UI can ask, and the queue a message enters."""
        ...
