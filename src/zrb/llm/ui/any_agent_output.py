"""The narrow UI contract that non-UI code is allowed to depend on.

`zrb.llm.tool_call` types its UI parameters as this instead of `AnyUI`, so
pyright rejects reaching past these three methods. Size capped by
`test/architecture/test_agent_output_surface.py`.
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
