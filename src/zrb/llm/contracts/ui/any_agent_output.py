"""The narrow UI contract that non-UI code is allowed to depend on.

`zrb.llm.tool_call` types its UI parameters as this instead of `AnyUI`, so
pyright rejects reaching past the writer and the input role. Size capped by
`test/architecture/test_agent_output_surface.py`.

The input accessor is inherited from `AnyUIMessageSink`, not declared again:
two contracts promising the same member is the drift `test_ui_contract_roles.py`
exists to stop, and a sub-agent's message and a tool call's question enter
through the same queue.
"""

from __future__ import annotations

from typing import Protocol, TextIO, runtime_checkable

from zrb.llm.contracts.ui.any_ui_message_sink import AnyUIMessageSink


@runtime_checkable
class AnyAgentOutput(AnyUIMessageSink, Protocol):
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
