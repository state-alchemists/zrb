"""The output surface of a `BaseUI`, reached as `ui.display`.

`BaseUI` keeps the two members a backend actually overrides — `append_to_output`
and `stream_to_parent` — because those are what a subclass supplies. Everything
built on top of them lives here: markdown, the turn's answer, the status bar's
badges, the echo span of a queued message, and the block markers a live turn
collapses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

from zrb.llm.any_ui_display import AnyUIDisplay
from zrb.llm.ui_fallback.state_defaults import UIStateDefaultsMixin
from zrb.util.cli.markdown import render_markdown

if TYPE_CHECKING:
    from collections.abc import Sequence

    from zrb.llm.agent.types import ModelMessage
    from zrb.llm.ui.base.message_queue import QueuedMessage
    from zrb.llm.ui.base.ui import BaseUI


class BaseUIDisplay(UIStateDefaultsMixin, AnyUIDisplay):
    """Whatever a `BaseUI` writes, minus the two primitives it writes through.

    An override of `append_to_output` or `stream_to_parent` on the host still
    decides where the text lands; this part only decides what the text is.
    """

    def __init__(self, base_ui: "BaseUI") -> None:
        self._base_ui = base_ui

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Write through the host, whose override is the backend's writer."""
        self._base_ui.append_to_output(
            *values, sep=sep, end=end, file=file, flush=flush, kind=kind
        )

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Stream through the host, which decides what "the parent" means."""
        self._base_ui.stream_to_parent(
            *values, sep=sep, end=end, file=file, flush=flush, kind=kind
        )

    @property
    def last_output(self) -> str:
        """The last turn's answer, or "" before any turn has completed."""
        data = self._base_ui.last_result_data
        if data is None:
            return ""
        return data

    def append_markdown(self, markdown_text: str) -> None:
        """Render `markdown_text` at this UI's output width and append it."""
        self._base_ui.append_to_output(
            render_markdown(
                markdown_text,
                width=self._base_ui.output_field_width,
                theme=self._base_ui.markdown_theme,
            )
        )

    def append_answer(self, markdown_text: str) -> None:
        """Append the turn's answer, the text the reader keeps.

        A UI that lays a run's output out in a column mixes in its own display
        part, so the answer lands in that column instead of the margin.
        """
        self.append_markdown(markdown_text)

    def replay_history(self, messages: "list[ModelMessage]") -> None:
        """Show a resumed conversation through the live-render paths.

        Through the host, because a UI that seeds its input recall from the
        loaded turns overrides `replay_history` there, and reaching the
        renderer directly would skip that.
        """
        self._base_ui.replay_history(messages)

    def set_status_badge(self, key: str, text: str | None) -> None:
        """Show `text` under `key` in the status bar, then repaint."""
        self._base_ui.status_bar.set_badge(key, text)
        self.invalidate_ui()

    def invalidate_ui(self) -> None:
        """Ask the host to repaint; a UI with no live surface does nothing."""
        self._base_ui.invalidate_ui()

    # The four echo hooks are overridable on the host: a UI that keeps an output
    # buffer overrides them there, and the defaults on `UIStateDefaultsMixin`
    # answer for one that keeps none. The part only decides when they are called.

    def track_echo_span(self, entry: "QueuedMessage", echo: str) -> None:
        """Record the output-buffer span of `echo` on `entry`."""
        self._base_ui.track_echo_span(entry, echo)

    def track_rendered_echo(self, entry: "QueuedMessage", header: str) -> None:
        """Record the span of an echo whose body was rendered as Markdown."""
        self._base_ui.track_rendered_echo(entry, header)

    def redraw_echo(self, entry: "QueuedMessage") -> str | None:
        """Rewrite `entry`'s echoed line, or None when it cannot be spliced."""
        return self._base_ui.redraw_echo(entry)

    def remove_echo(self, entry: "QueuedMessage") -> None:
        """Take `entry`'s echoed line out of this UI's output."""
        self._base_ui.remove_echo(entry)

    def redraw_echoes(self, entries: "Sequence[QueuedMessage]") -> None:
        """Rewrite each entry's echo on every UI, through the host.

        Which UIs share a queue is a fact about the UI tree, not about one
        surface, so the fan-out stays where the host keeps its graph.
        """
        self._base_ui.redraw_echoes(entries)
