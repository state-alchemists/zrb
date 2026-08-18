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
        session_id: str = "",
    ):
        self._wrapped = wrapped_ui
        self._prefix = prefix
        self._buffer: list[str] = []
        self._merged_output: str = ""
        # Set by _run_agent_task so buffered output also feeds the activity panel.
        self._agent_id: str | None = None
        # Scopes activity-panel updates to the session that started this
        # delegation, so a process hosting multiple sessions doesn't bleed one
        # session's sub-agent activity into another's.
        self._session_id = session_id
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

    @property
    def parent_ui(self) -> UIProtocol:
        """The UI this buffer flushes to (the parent agent's UI).

        Public counterpart of the ``wrapped_ui`` constructor argument, so the
        live-session continuation path can hand the parent UI a synthesized
        message (``submit_message``) without reading ``_wrapped``.
        """
        return self._wrapped

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        # The lock guards only the synchronous write below (prevents two
        # sibling fan-out agents' output_to_parent writes from interleaving)
        # — it must NOT wrap the wait for the human's answer. Holding it
        # across that wait serialized every sibling's ENTIRE approval
        # round-trip through whichever one acquired the lock first: the
        # others never even reached the shared confirmation queue, so
        # picking a different sub-agent via the picker had nothing of that
        # agent's own to resolve yet.
        async with self._lock:
            # Write the caller's approval/question message straight to the
            # parent so the user sees *what* is being approved without
            # navigating into the sub-agent's live view.
            if output_to_parent:
                self._wrapped.append_to_output(output_to_parent, end="")
            prefixed_prompt = (
                f"{self._prefix}{prompt}"
                if self._prefix and prompt.strip() != ""
                else prompt
            )
        # Preserve the originating agent's id through nested delegation (a
        # sub-agent's own sub-agent) instead of relabeling it as this layer's
        # — only stamp `self._agent_id` at the layer closest to the actual
        # caller. Awaited outside the lock so siblings can enqueue concurrently.
        return await self._wrapped.ask_user(
            prefixed_prompt,
            agent_id=agent_id if agent_id is not None else self._agent_id,
        )

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
        # lazy: circular — buffered_ui → output → ... → buffered_ui
        from zrb.llm.ui.default.output import _merge_output_chunk

        self._merged_output = _merge_output_chunk(self._merged_output, text)
        self._buffer.append(text)
        if self._agent_id:
            agent_activity_registry.update(
                self._agent_id, text, session_id=self._session_id
            )

    async def ask_user_choice(
        self, spec: ChoiceSpec, agent_id: str | None = None
    ) -> str:
        # No synchronous parent-write to guard here (unlike ask_user's
        # output_to_parent), so nothing needs the lock — same reasoning as
        # ask_user: the wait for the human's answer must never be held under
        # it, or sibling fan-out agents can't reach the shared confirmation
        # queue concurrently.
        return await self._wrapped.ask_user_choice(
            spec, agent_id=agent_id if agent_id is not None else self._agent_id
        )

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        return await self._wrapped.run_interactive_command(cmd, shell)

    async def run_async(self) -> Any:
        return await self._wrapped.run_async()

    def get_buffered_output(self) -> str:
        """Get all buffered output."""
        return self._merged_output

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
        self._merged_output = ""

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
        """High-priority status messages (e.g. a tool-call notification mid
        sub-agent execution) — same destination as `append_to_output` now.

        Used to bypass the buffer and write straight to the parent UI, on the
        theory that a slow-operation status line should be visible
        immediately. That theory turned out wrong in practice: it made
        routine sub-agent chatter (search queries, fetch status) leak into
        the main transcript, which is exactly the noise a human navigating
        into this sub-agent's own live view (its buffer, via
        `get_buffered_output()`) should see there instead — not in main.
        """
        self.append_to_output(
            *values, sep=sep, end=end, file=file, flush=flush, kind=kind
        )
