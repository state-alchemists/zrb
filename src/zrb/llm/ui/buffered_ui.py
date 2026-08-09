"""A `UIProtocol` that buffers its output instead of writing it through.

Used when several sub-agents run in parallel: each gets one of these, so their
interleaved output is collected and flushed as a block rather than shredded
across the terminal, while `ask`-style prompts are forwarded to the real UI one
at a time under a shared lock.

Lived inside `llm/tool/delegate.py` until 2.58.0 — a complete UI implementation
in a tool module, which is also an import edge pointing the wrong way.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TextIO

from zrb.llm.agent.activity import agent_activity_registry
from zrb.llm.tool_call.ui_protocol import UIProtocol

if TYPE_CHECKING:
    from zrb.llm.tool_call.ui_protocol import ChoiceSpec


class BufferedUI(UIProtocol):
    """UI wrapper that buffers all output and forwards asks to parent sequentially."""

    def __init__(
        self,
        wrapped_ui: UIProtocol,
        prefix: str = "",
        shared_lock: asyncio.Lock | None = None,
    ):
        self._wrapped = wrapped_ui
        self._prefix = prefix
        self._buffer: list[str] = []
        # Set by _run_agent_task so buffered output also feeds the activity panel.
        self._agent_id: str | None = None
        # Use provided shared lock (for parallel agents) or create own lock
        self._lock = shared_lock if shared_lock is not None else asyncio.Lock()

    def set_activity_id(self, agent_id: str) -> None:
        """Route this sub-agent's output lines to the activity registry."""
        self._agent_id = agent_id

    def set_label(self, prefix: str) -> None:
        """Set the per-line output prefix (e.g. ``[generalist #1] ``)."""
        self._prefix = prefix

    @property
    def label(self) -> str:
        """The output prefix without surrounding whitespace (e.g. ``[generalist #1]``)."""
        return self._prefix.strip()

    async def ask_user(self, prompt: str) -> str:
        # Lock ensures only one agent interacts with parent UI at a time
        # This prevents interleaved output when multiple parallel agents need approval
        async with self._lock:
            # Flush buffered output so user can see what they're being asked about
            self.flush_to_parent()
            prefixed_prompt = (
                f"{self._prefix}{prompt}"
                if self._prefix and prompt.strip() != ""
                else prompt
            )
            return await self._wrapped.ask_user(prefixed_prompt)

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        text = sep.join(str(v) for v in values) + end
        self._buffer.append(text)
        if self._agent_id:
            agent_activity_registry.update(self._agent_id, text)

    async def ask_user_choice(self, spec: ChoiceSpec) -> str:
        # Mirrors ask_user: serialize parent interaction and flush first.
        async with self._lock:
            self.flush_to_parent()
            return await self._wrapped.ask_user_choice(spec)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        return await self._wrapped.run_interactive_command(cmd, shell)

    async def run_async(self) -> Any:
        return await self._wrapped.run_async()

    def get_buffered_output(self) -> str:
        """Get all buffered output."""
        return "".join(self._buffer)

    def flush_to_parent(self) -> None:
        """Flush buffered output to parent UI."""
        output = self.get_buffered_output()
        if output:
            if self._prefix:
                indented = "\n".join(
                    f"{self._prefix}{line}" if line.strip() != "" else ""
                    for line in output.split("\n")
                )
                self._wrapped.append_to_output(indented)
            else:
                self._wrapped.append_to_output(output)
            self._buffer.clear()

    def clear_buffer(self) -> None:
        """Clear the buffer without flushing."""
        self._buffer.clear()

    @property
    def yolo(self) -> bool | frozenset:
        """Delegate YOLO mode to the wrapped parent UI."""
        if hasattr(self._wrapped, "yolo"):
            return getattr(self._wrapped, "yolo")
        return False

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ) -> None:
        """Immediately stream output to parent UI, bypassing the buffer.

        Use this for high-priority status messages that should be visible
        immediately, such as tool call notifications during subagent execution.
        """
        text = sep.join(str(v) for v in values) + end
        if self._agent_id:
            agent_activity_registry.update(self._agent_id, text)
        if self._prefix:
            lines = text.split("\n")
            text = "\n".join(
                f"{self._prefix}{line}" if line.strip() else "" for line in lines
            )
        self._wrapped.append_to_output(text, kind=kind)
