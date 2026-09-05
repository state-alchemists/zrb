"""The narrow UI contract that non-UI code is allowed to depend on.

`BaseUI` exposes 135 public methods. Everything outside `zrb.llm.ui` uses 12 of
them, and `zrb.llm.tool_call` uses the three below. Typing a parameter as
`AnyAgentOutput` instead of `AnyUI` is what keeps that true: pyright fails the
build when a consumer reaches for a fourth method.

Adding a member here is a design decision, not a convenience. The architecture
ratchet in `test/architecture/test_agent_output_surface.py` caps the size.

Mirrors the pattern in `zrb.llm.agent.activity.HasActivityTracking`, but named
`Any<Thing>` rather than `Has<Thing>` since it is used as a parameter/slot
type throughout `zrb.llm.tool_call` (R9), not just an `isinstance` capability
probe.
"""

from __future__ import annotations

from typing import Any, Protocol, TextIO, runtime_checkable


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

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Ask the user a free-text question and return their answer."""
        ...

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run an interactive command, handing it the real terminal."""
        ...
