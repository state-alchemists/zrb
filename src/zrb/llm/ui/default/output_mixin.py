"""Output rendering for the default `UI`.

Carries the logic for appending text to the read-only output buffer
(`append_to_output`) and rendering the info / status bars. Kept separate
from `default_ui.py` so the prompt-toolkit Application setup stays focused.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, TextIO

from zrb.config.config import CFG
from zrb.llm.hook.interface import HookEvent
from zrb.util.cli.style import stylize_faint
from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from typing import Any

    from prompt_toolkit.formatted_text import AnyFormattedText
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)


class OutputMixin:
    """Renders the output field, info bar, and status bar for the default UI."""

    # Host-class contract: state owned by `BaseUI.__init__` and the default
    # `UI.__init__` (prompt-toolkit widgets). Declared here so static type
    # checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        # From BaseUI
        _assistant_name: str
        _conversation_session_name: str
        _current_confirmation: asyncio.Future[str] | None
        _confirmation_output_buffer: list[str]
        _cwd: str
        _git_info: str
        _is_thinking: bool
        _model: "Model | str | None"
        # From default UI (prompt_toolkit widgets — typed as Any to avoid
        # importing heavyweight modules at type-check time).
        _input_field: Any
        _output_field: Any

    @property
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""
        return self._is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool) -> None:
        self._is_thinking = value

    @property
    def current_confirmation(self) -> "asyncio.Future[str] | None":
        """The pending tool-call confirmation future, if any."""
        return self._current_confirmation

    @current_confirmation.setter
    def current_confirmation(self, value: "asyncio.Future[str] | None") -> None:
        self._current_confirmation = value

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
        # lazy: heavy third-party
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

        # Buffer main-agent output while a confirmation is pending during
        # streaming, so the confirmation prompt is not interleaved with tokens.
        if self._current_confirmation is not None and self._is_thinking:
            self._confirmation_output_buffer.append(content)
            self._schedule_invalidate()
            return

        if kind != "text":

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
        self._schedule_invalidate()

    def _schedule_invalidate(self):
        if self._pending_invalidate:
            return
        self._pending_invalidate = True

        async def _do_invalidate():
            await asyncio.sleep(0.016)
            self._pending_invalidate = False
            self.invalidate_ui()

        try:
            self._invalidate_task = asyncio.create_task(_do_invalidate())
        except RuntimeError:
            self._pending_invalidate = False
            self.invalidate_ui()

    @property
    def output_field_width(self) -> int | None:
        """Get the output field width."""
        try:
            width = get_terminal_size().columns - 4
            if width < 10:
                width = None
        except Exception:
            width = None
        return width

    def get_info_bar_text(self) -> "AnyFormattedText":
        # lazy: heavy third-party
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

    def get_status_bar_text(self) -> "AnyFormattedText":
        if self.current_confirmation is not None:
            dots = getattr(self, "_confirmation_dots", 0)
            next_dots = (dots + 1) % 4
            setattr(self, "_confirmation_dots", next_dots)
            dot_str = "." * next_dots + " " * (3 - next_dots)
            return [
                (
                    CFG.LLM_UI_STYLE_CONFIRMATION,
                    f" 👋 {self._assistant_name} is waiting for confirmation{dot_str} ",
                )
            ]
        if self.is_thinking:
            dots = getattr(self, "_thinking_dots", 0)
            next_dots = (dots + 1) % 4
            setattr(self, "_thinking_dots", next_dots)
            dot_str = "." * next_dots + " " * (3 - next_dots)
            return [
                (
                    CFG.LLM_UI_STYLE_THINKING,
                    f" ⏳ {self._assistant_name} is working{dot_str} ",
                ),
            ]
        return [(CFG.LLM_UI_STYLE_STATUS, " 🚀 Ready ")]
