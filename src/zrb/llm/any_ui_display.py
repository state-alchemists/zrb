"""The UI's output surface: what a backend must render."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Sequence

    from zrb.llm.agent.types import ModelMessage
    from zrb.llm.ui.base.message_queue import QueuedMessage


class AnyUIDisplay(ABC):
    """Everything a UI writes, and the block markers it writes around."""

    @abstractmethod
    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Write output the way `print()` would, kept for later replay."""

    @abstractmethod
    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Write output to a delegating parent UI, not this UI's own stream."""

    @abstractmethod
    def flush_to_parent(self) -> None:
        """Write anything buffered here out to the delegating parent UI.

        A no-op for UIs that stream directly rather than buffering.
        """

    @abstractmethod
    def append_markdown(self, markdown_text: str) -> None:
        """Show *markdown_text*. A pane that renders Markdown itself takes the
        source; any other UI renders it and writes the text."""

    @abstractmethod
    def append_answer(self, markdown_text: str) -> None:
        """Show the turn's answer, where the streamed copy was if the UI lays a
        run's output out in a column."""

    @abstractmethod
    def record_tool_call_block(self, collapsed: str, full: str) -> None:
        """Print a tool-call/result line a toggle-capable UI can later expand."""

    @abstractmethod
    def invalidate_ui(self) -> None:
        """Ask this UI to repaint. A no-op for UIs with no live surface."""

    @abstractmethod
    def set_status_badge(self, key: str, text: str | None) -> None:
        """Show *text* in the status bar under *key*, replacing what *key*
        showed before; ``None`` takes it away. For a feature's one-line state.
        A no-op for UIs with no status bar.
        """

    @abstractmethod
    def set_stream_indentation(self, indent: str) -> None:
        """Learn the column a run's streamed lines wrap at."""

    @abstractmethod
    def mark_thinking_block_start(self) -> None:
        """Note where a live thinking block begins."""

    @abstractmethod
    def collapse_thinking_block(self, collapsed: str, full: str) -> bool | None:
        """Collapse the block `mark_thinking_block_start` opened.

        Returns whether a block was collapsed, or None for a UI that tracks none.
        """

    @abstractmethod
    def mark_text_block_start(self) -> None:
        """Note where the reply's text block begins."""

    @abstractmethod
    def collapse_text_block(self, collapsed: str, full: str) -> bool | None:
        """Collapse the block `mark_text_block_start` opened.

        Returns whether a block was collapsed, or None for a UI that tracks none.
        """

    @abstractmethod
    def settle_text_block(self, source: str) -> None:
        """Keep a text block that a tool call ended, rendering *source* in full."""

    @property
    @abstractmethod
    def last_output(self) -> str:
        """The last answer this UI rendered, or "" when it has none."""

    @abstractmethod
    def replay_history(self, messages: "list[ModelMessage]") -> None:
        """Show a resumed conversation."""

    @abstractmethod
    def track_echo_span(self, entry: "QueuedMessage", echo: str) -> None:
        """Record the output-buffer span of `echo` on `entry` for `redraw_echo`.

        A UI with no output buffer leaves the entry untouched.
        """

    @abstractmethod
    def track_rendered_echo(self, entry: "QueuedMessage", header: str) -> None:
        """Record the span of an echo whose body was rendered as Markdown.

        *header* is the verbatim part written before the rendered body. The
        counterpart of `track_echo_span` for an echo that landed rendered.
        """

    @abstractmethod
    def redraw_echo(self, entry: "QueuedMessage") -> str | None:
        """Rewrite `entry`'s echoed line from its current text.

        Returns the rewritten line, or None when it could not be spliced in
        place; the caller then echoes afresh.
        """

    @abstractmethod
    def redraw_echoes(self, entries: "Sequence[QueuedMessage]") -> None:
        """Rewrite the echoed lines of *entries* just delivered into a turn."""

    @abstractmethod
    def remove_echo(self, entry: "QueuedMessage") -> None:
        """Take `entry`'s echoed line out of this UI's output.

        Called when a still-queued message is dropped. A UI with no output
        buffer leaves the entry alone.
        """
