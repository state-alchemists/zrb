"""Output rendering for the default `UI`.

Carries the logic for appending text to the read-only output buffer
(`append_to_output`) and rendering the info / status bars. Kept separate
from `default_ui.py` so the prompt-toolkit Application setup stays focused.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, TextIO

from zrb.llm.hook.interface import HookEvent
from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import AnyFormattedText

logger = logging.getLogger(__name__)


class OutputMixin:
    """Renders the output field, info bar, and status bar for the default UI."""

    @property
    def output_text(self) -> str:
        """Get the current text in the output field."""
        return self._output_field.text

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        from prompt_toolkit.application import get_app
        from prompt_toolkit.document import Document

        current_text = self._output_field.text

        # Scroll to end when the input field is focused or we're already at the
        # last line. Otherwise preserve the user's scroll position.
        is_input_focused = False
        try:
            app = get_app()
            is_input_focused = app.layout.has_focus(self._input_field)
        except Exception:
            pass

        is_at_last_line = False
        try:
            doc = self._output_field.buffer.document
            is_at_last_line = doc.cursor_position_row >= doc.line_count - 1
        except Exception:
            pass

        should_scroll_to_end = is_input_focused or is_at_last_line

        content = sep.join([str(value) for value in values]) + end
        if kind != "text":
            from zrb.util.cli.style import stylize_faint

            content = stylize_faint(content)

        # Handle carriage returns (\r) for status updates
        if "\r" in content:
            last_newline = current_text.rfind("\n")
            if last_newline == -1:
                previous = ""
                last = current_text
            else:
                previous = current_text[: last_newline + 1]
                last = current_text[last_newline + 1 :]
            combined = last + content
            resolved = re.sub(r"[^\n]*\r", "", combined)
            new_text = previous + resolved
        else:
            new_text = current_text + content

        try:
            self.execute_hook(
                HookEvent.NOTIFICATION,
                {"content": content, "session": self._conversation_session_name},
                session_id=self._conversation_session_name,
                cwd=self._cwd,
            )
        except Exception as e:
            logger.error(f"Failed to trigger notification hook: {e}")

        new_cursor_position = (
            len(new_text)
            if should_scroll_to_end
            else self._output_field.buffer.cursor_position
        )
        new_cursor_position = min(max(0, new_cursor_position), len(new_text))

        self._output_field.buffer.set_document(
            Document(new_text, cursor_position=new_cursor_position),
            bypass_readonly=True,
        )
        self.invalidate_ui()

    @property
    def output_field_width(self) -> int | None:
        """Get the output field width."""
        return self._get_output_field_width()

    def _get_output_field_width(self) -> int | None:
        try:
            width = get_terminal_size().columns - 4
            if width < 10:
                width = None
        except Exception:
            width = None
        return width

    def _get_info_bar_text(self) -> "AnyFormattedText":
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.formatted_text.utils import fragment_list_width

        model_name = "Unknown"
        if self._model:
            if isinstance(self._model, str):
                model_name = self._model
            elif hasattr(self._model, "model_name"):
                model_name = getattr(self._model, "model_name")
            else:
                model_name = str(self._model)

        _yolo = self.yolo
        if _yolo is True:
            yolo_text = "<style color='ansired'><b>ON </b></style>"
        elif isinstance(_yolo, frozenset) and _yolo:
            tools_str = ",".join(sorted(_yolo))
            yolo_text = f"<style color='ansiyellow'><b>[{tools_str}]</b></style>"
        else:
            yolo_text = "<style color='ansigreen'>OFF</style>"

        line1_html = (
            f" 🤖 <b>Model:</b> {model_name} "
            f"| 💬 <b>Session:</b> {self._conversation_session_name} "
            f"| 🤠 <b>YOLO:</b> {yolo_text}"
        )
        line2_html = (
            f" 📂 <b>Dir:</b> {self._cwd} " f"| 🌿 <b>Git:</b> {self._git_info}"
        )

        total_cols = get_terminal_size().columns

        def center_line(html_text: str) -> str:
            fragments = HTML(html_text).__pt_formatted_text__()
            visible_width = fragment_list_width(fragments)
            padding = max(0, (total_cols - visible_width) // 2)
            return (
                " " * padding + html_text + " " * (total_cols - visible_width - padding)
            )

        return HTML(center_line(line1_html) + "\n" + center_line(line2_html))

    def _get_status_bar_text(self) -> "AnyFormattedText":
        if self._is_thinking:
            return [("class:thinking", f" ⏳ {self._assistant_name} is working... ")]
        return [("class:status", " 🚀 Ready ")]
