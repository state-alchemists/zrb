"""Key bindings for the default `UI`.

`setup_app_keybindings` wires the prompt-toolkit handlers; it stays one
method because each handler is a closure capturing `self` and the event
object. The dispatch logic for Enter — which routes through the slash
command handlers on `BaseUI._commands_mixin` — is the bulk of the file.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from zrb.llm.hook.interface import HookEvent
from zrb.llm.util.image_scale import scale_image_bytes

if TYPE_CHECKING:
    from typing import Any

    from prompt_toolkit.key_binding import KeyBindings
    from pydantic_ai.messages import UserContent

    from zrb.task.any_task import AnyTask


class KeybindingsMixin:
    """Application key bindings for the default UI."""

    # Host-class contract: state owned by `BaseUI.__init__` and the default
    # `UI.__init__`. Declared here so static type checkers can verify
    # accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        # From BaseUI
        _background_tasks: set[asyncio.Task]
        _conversation_session_name: str
        _is_thinking: bool
        _pending_attachments: list["UserContent"]
        _running_llm_task: asyncio.Task | None
        # From default UI (prompt_toolkit widgets)
        _input_field: Any
        _output_field: Any

        # From CommandsMixin
        def classify_input(self, text: str) -> str: ...

        def schedule_command(self, text: str) -> None: ...

        def _submit_user_message(self, llm_task: "AnyTask", text: str) -> None: ...

    def setup_app_keybindings(
        self, app_keybindings: "KeyBindings", llm_task: "AnyTask"
    ):
        @app_keybindings.add("f6")
        def _(event):
            if event.app.layout.has_focus(self._input_field):
                event.app.layout.focus(self._output_field)
            else:
                event.app.layout.focus(self._input_field)

        @app_keybindings.add("c-c")
        @app_keybindings.add("escape", "c")
        def _(event):
            buffer = event.app.current_buffer
            if buffer.selection_state:
                data = buffer.copy_selection()
                if event.app.clipboard:
                    event.app.clipboard.set_data(data)
                buffer.exit_selection()
                return
            if buffer.text != "":
                buffer.reset()
                return
            self._cancel_pending_confirmations()
            if self._running_llm_task and not self._running_llm_task.done():
                self._running_llm_task.cancel()
                self.append_to_output("\n<Esc> Canceled")
            self.execute_hook(
                HookEvent.STOP,
                {"reason": "ctrl_c", "session": self._conversation_session_name},
            )
            event.app.exit()

        @app_keybindings.add("c-v")
        @app_keybindings.add("escape", "v")
        def _(event):
            # Capture clipboard synchronously: prompt_toolkit may recycle the
            # event object before the async handler runs.
            clipboard = event.app.clipboard

            async def _handle_paste():
                # lazy: tests patch `zrb.llm.util.clipboard.get_clipboard_image`
                # at the source path; hoisting would bind the name at
                # module-load and bypass the mock.
                # lazy: zrb internal (heavy via transitive / circular)
                from zrb.llm.util.clipboard import (
                    get_clipboard_image,
                    missing_tool_hint,
                )
                from zrb.util.cli.style import stylize_error, stylize_faint

                img_bytes = await get_clipboard_image()
                if img_bytes is not None:
                    # lazy: heavy third-party
                    from pydantic_ai import BinaryContent

                    scaled = scale_image_bytes(img_bytes, media_type="image/png")
                    attachment = BinaryContent(
                        data=scaled.data, media_type=scaled.media_type
                    )
                    self._pending_attachments.append(attachment)
                    size_kb = scaled.final_bytes / 1024
                    if scaled.scaled:
                        saved_kb = scaled.saved_bytes / 1024
                        msg = (
                            f"\n  📸 Image pasted from clipboard ({size_kb:.1f} KB, "
                            f"scaled — saved {saved_kb:.1f} KB)\n"
                        )
                    else:
                        msg = f"\n  📸 Image pasted from clipboard ({size_kb:.1f} KB)\n"
                    self.append_to_output(stylize_faint(msg))
                    self.invalidate_ui()
                else:
                    hint = missing_tool_hint()
                    if hint:
                        self.append_to_output(
                            stylize_error(f"\n  ❌ No image in clipboard.\n{hint}")
                        )
                        self.invalidate_ui()
                    elif clipboard:
                        # No image found — paste text into input field. Always
                        # target input_field, not current_buffer, since focus
                        # may be on the read-only output field.
                        # lazy: heavy third-party
                        from prompt_toolkit.application import get_app as _get_app

                        _get_app().layout.focus(self._input_field)
                        self._input_field.buffer.paste_clipboard_data(
                            clipboard.get_data()
                        )

            task = asyncio.get_event_loop().create_task(_handle_paste())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        @app_keybindings.add("escape")
        def _(event):
            self._cancel_pending_confirmations()
            if self._running_llm_task and not self._running_llm_task.done():
                self._running_llm_task.cancel()
                self.execute_hook(
                    HookEvent.STOP,
                    {
                        "reason": "escape",
                        "session": self._conversation_session_name,
                    },
                )
                self.append_to_output("\n<Esc> Canceled")

        @app_keybindings.add("enter")
        def _(event):
            if self._handle_multiline(event):
                return

            if self._handle_confirmation(event):
                return

            buff = event.current_buffer
            text = buff.text
            if not text.strip():
                return

            # Route by recognition, not by "/" prefix — command tokens are
            # user-configurable (e.g. ">" for redirect). Recognized commands go
            # through the hook-wrapped async dispatch (PreCommand may block;
            # PostCommand fires after); plain text is sent to the LLM.
            kind = self.classify_input(text)

            # Run-while-thinking commands (/btw, YOLO toggle) dispatch even while
            # the LLM is responding.
            if kind == "thinking_command":
                buff.reset()
                self.schedule_command(text)
                return

            # Everything else is gated while thinking (matches main: the buffer
            # is kept so the user can resubmit once the response finishes).
            if self._is_thinking:
                return

            if kind == "command":
                buff.reset()
                self.schedule_command(text)
                return

            # Plain message — record for up-arrow recall, then submit.
            buff.append_to_history()
            self._submit_user_message(llm_task, text)
            buff.reset()

        @app_keybindings.add("c-y")
        def _(event):
            self.toggle_yolo()

        @app_keybindings.add("c-j")  # Ctrl+J / Ctrl+Enter (Linefeed)
        @app_keybindings.add("c-space")  # Ctrl+Space (Fallback)
        def _(event):
            event.current_buffer.insert_text("\n")

    def _handle_multiline(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        # Trailing backslash → newline-with-cursor-at-end (multiline indicator)
        if text.strip().endswith("\\"):
            if buff.cursor_position == len(text):
                if text.endswith("\\"):
                    buff.delete_before_cursor(count=1)
                    buff.insert_text("\n")
                    return True
        return False
