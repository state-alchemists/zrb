"""Inert display role: a UI that renders nothing of its own.

Everything here writes nothing, and the three that do write go through the host's
`append_to_output`, which `AnyUIDisplay` declares abstract. A UI that draws a
terminal, a buffer or a log file overrides what it renders for real and wins on
MRO.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO, cast

from zrb.llm.ui.fallback.echo_broadcast import broadcast_echo

if TYPE_CHECKING:
    from collections.abc import Sequence

    from zrb.llm.agent.types import ModelMessage
    from zrb.llm.ui.any_ui import AnyUI
    from zrb.llm.ui.any_ui_display import AnyUIDisplay
    from zrb.llm.ui.base.message_queue import QueuedMessage


class UIDisplayDefaults:
    """The display role for a UI with no output surface of its own."""

    _uidefaults_last_output: str = ""

    if TYPE_CHECKING:

        def append_to_output(
            self,
            *values: object,
            sep: str = " ",
            end: str = "\n",
            file: TextIO | None = None,
            flush: bool = False,
            kind: str = "text",
        ):
            """The host's writer, which the display role declares abstract."""

    @property
    def display(self) -> "AnyUIDisplay":
        """A UI that keeps its own output surface is its own display."""
        return cast("AnyUIDisplay", self)

    @property
    def last_output(self) -> str:
        """Nothing rendered."""
        return self._uidefaults_last_output

    def invalidate_ui(self) -> None:
        """No surface to repaint."""

    def set_status_badge(self, key: str, text: str | None) -> None:
        """No status bar to show a badge in."""

    def flush_to_parent(self) -> None:
        """Nothing buffered, so nothing to hand upward."""

    def append_markdown(self, markdown_text: str) -> None:
        """Render *markdown_text* and write the text."""
        # lazy: transitively heavy -- the renderer pulls the theme and the
        # markdown stack.
        from zrb.util.cli.markdown import render_markdown

        self.append_to_output(render_markdown(markdown_text, width=None), end="")

    def append_answer(self, markdown_text: str) -> None:
        """No column layout: the answer is shown like any other Markdown."""
        self.append_markdown(markdown_text)

    def record_tool_call_block(self, collapsed: str, full: str) -> None:
        """Nothing to expand later: write the collapsed form as a `tool_call` line."""
        self.append_to_output(collapsed, end="", kind="tool_call")

    def set_stream_indentation(self, indent: str) -> None:
        """No wrapping of its own to adjust."""

    def mark_thinking_block_start(self) -> None:
        """No live thinking block to place."""

    def collapse_thinking_block(self, collapsed: str, full: str) -> bool | None:
        """No block tracked: the thinking text stays as streamed."""
        return None

    def mark_text_block_start(self) -> None:
        """No text block to place."""

    def collapse_text_block(self, collapsed: str, full: str) -> bool | None:
        """No block tracked: the streamed text stays as it is."""
        return None

    def settle_text_block(self, source: str) -> None:
        """The streamed copy stays as it is."""

    def replay_history(self, messages: "list[ModelMessage]") -> None:
        """Write the resumed conversation as plain text."""
        # lazy: zrb.llm.util.history_formatter transitively loads pydantic_ai.
        from zrb.llm.util.history_formatter import format_history_as_text

        self.append_to_output(format_history_as_text(messages))

    def track_echo_span(self, entry: "QueuedMessage", echo: str) -> None:
        """No output buffer to record an echo span against."""

    def track_rendered_echo(self, entry: "QueuedMessage", header: str) -> None:
        """No output buffer to record a rendered echo span against."""

    def redraw_echo(self, entry: "QueuedMessage") -> str | None:
        """No output buffer to splice a rewritten echo into."""
        return None

    def redraw_echoes(self, entries: "Sequence[QueuedMessage]") -> None:
        """Rewrite the echoes of `entries` on every UI that holds one.

        A delivered message leaves the queue, so its panel row disappears at
        once; its echo line keeps its place in the transcript and changes marker
        (`DELIVERED_MARKER`), the only record of what the model actually read.
        The children of one `MultiUI` each hold their own echo, so the redraw
        goes to all of them rather than to the UI it was called on.
        """
        for entry in entries:
            # Each entry is bound to its own call, so a deferred redraw — this
            # one queued, or a task — cannot reach the loop's last entry.
            broadcast_echo(
                cast("AnyUI", self),
                lambda ui, entry=entry: ui.display.redraw_echo(entry),
            )

    def remove_echo(self, entry: "QueuedMessage") -> None:
        """No output buffer to take a dropped echo out of."""
