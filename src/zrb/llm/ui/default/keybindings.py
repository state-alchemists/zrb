"""Key bindings for the default `UI`.

`setup_app_keybindings` is a registration table: it wires each
prompt-toolkit key to a thin closure that delegates to a named `_on_*`
handler method. The involved handlers (Enter dispatch, clipboard paste,
voice push-to-talk) live in those methods rather than as nested
closures, so each is a reviewable, individually testable unit.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.hook.interface import HookEvent
from zrb.llm.tool.ambient_state import get_session_ownership_key
from zrb.llm.util.image_scale import scale_image_bytes
from zrb.util.cli.style import remove_style, stylize_error, stylize_muted

if TYPE_CHECKING:
    from typing import Any

    from prompt_toolkit.key_binding import KeyBindings

    from zrb.llm.ui.default.ui import UI
    from zrb.task.any_task import AnyTask


class UIKeybindings:
    """Application key bindings for the default UI."""

    _KEY_REPEAT_DEBOUNCE = 0.3

    def __init__(self, ui: "UI") -> None:
        self._ui = ui
        self._voice_last_press: float = 0.0
        self._voice_engine: "Any | None" = None

    def setup_app_keybindings(  # noqa: C901 -- registration/factory fn; mccabe counts each nested handler def, radon scores each separately (near-trivial on its own)
        self, app_keybindings: "KeyBindings", llm_task: "AnyTask"
    ):
        # lazy: heavy third-party
        from prompt_toolkit.filters import Condition, has_completions

        ui = self._ui

        # A choice widget owns Enter/space/Up/Down while active; the handlers
        # below apply when focus has moved to another pane, and the pane-local
        # bindings wire the same actions into the input/output controls.
        viewing_sub_agent = Condition(
            lambda: getattr(ui, "viewing_agent_id", None) is not None
        )
        active_choice = Condition(
            lambda: getattr(ui, "selection_part", None) is not None
            and ui.selection_part.has_active_choice()
        )
        no_active_choice = ~active_choice

        @app_keybindings.add("up", filter=active_choice)
        def _(event):
            self._on_choice_cursor(event, -1)

        @app_keybindings.add("down", filter=active_choice)
        def _(event):
            self._on_choice_cursor(event, 1)

        @app_keybindings.add("enter", filter=active_choice)
        def _(event):
            self._on_choice_confirm(event)

        @app_keybindings.add("space", filter=active_choice)
        def _(event):
            self._on_choice_toggle(event)

        # Ctrl+K toggles focus between panes; the panes bind no Tab/Shift+Tab
        # traversal (app/layout.py, app/keybinding.py), so Shift+Tab stays free
        # for mode cycling.
        @app_keybindings.add("c-k", filter=no_active_choice)
        def _(event):
            self._on_toggle_focus(event)

        @app_keybindings.add("c-c")
        @app_keybindings.add("escape", "c")
        def _(event):
            self._on_copy_or_clear(event)

        @app_keybindings.add("c-d")
        def _(event):
            self._on_exit_if_empty(event)

        @app_keybindings.add("c-v")
        @app_keybindings.add("escape", "v")
        def _(event):
            # Capture clipboard synchronously: prompt_toolkit may recycle the
            # event object before the async handler runs.
            clipboard = event.app.clipboard
            task = asyncio.create_task(self._on_clipboard_paste(clipboard))
            ui.background_tasks.add(task)
            task.add_done_callback(ui.background_tasks.discard)

        @app_keybindings.add("escape")
        def _(event):
            self._on_escape(event)

        @app_keybindings.add("left", filter=viewing_sub_agent)
        def _(event):
            # Filtered so Left still moves the input cursor outside agent view.
            ui.exit_agent_view()

        @app_keybindings.add("enter", filter=no_active_choice)
        def _(event):
            self._on_enter(event, llm_task)

        @app_keybindings.add("c-y")
        def _(event):
            ui.toggle_yolo()

        # Ctrl+O toggles the collapsible block at (or just before) the output
        # cursor. Unfiltered: `toggle_collapsible_block` itself routes to the
        # viewed sub-agent's scope when one is shown.
        @app_keybindings.add("c-o")
        def _(event):
            ui.toggle_collapsible_block()

        if CFG.IS_TERMUX:
            # On Termux, Tab and Shift+Tab are indistinguishable (both byte 0x09),
            # so Shift+Tab never arrives — bind plain Tab to mode cycling there.
            @app_keybindings.add("tab", filter=no_active_choice & ~has_completions)
            def _(event):
                self._on_cycle_mode(event)

        else:
            # Shift+Tab cycles normal → accept-edits → plan. Gated so completion
            # menus and choice widgets keep their own back-tab navigation.
            @app_keybindings.add("s-tab", filter=no_active_choice & ~has_completions)
            def _(event):
                self._on_cycle_mode(event)

        @app_keybindings.add("c-j", filter=no_active_choice)  # Ctrl+J / Ctrl+Enter
        @app_keybindings.add("c-space", filter=no_active_choice)  # Ctrl+Space fallback
        def _(event):
            event.current_buffer.insert_text("\n")

        # Voice push-to-talk is press-to-start, press-to-stop: terminals send
        # no key-release event, so hold-to-talk is impossible. The transcript
        # lands in the input field for editing before Enter submits it.
        voice_ptt_key = CFG.LLM_VOICE_PUSH_TO_TALK_KEY.strip().lower()
        voice_mode_active = Condition(
            lambda: getattr(getattr(ui, "voice", None), "mode_active", False)
        )

        @app_keybindings.add(voice_ptt_key, filter=voice_mode_active & no_active_choice)
        def _(event):
            self._on_voice_ptt(event)

    def _on_choice_cursor(self, event: Any, delta: int) -> None:
        self._ui.selection_part.move_choice_cursor(delta)

    def _on_choice_confirm(self, event: Any) -> None:
        self._ui.selection_part.confirm_choice()

    def _on_choice_toggle(self, event: Any) -> None:
        self._ui.selection_part.toggle_choice_current()

    def _on_toggle_focus(self, event: Any) -> None:
        ui = self._ui
        if event.app.layout.has_focus(ui.input_field):
            event.app.layout.focus(ui.output_field)
        else:
            event.app.layout.focus(ui.input_field)

    def _on_copy_or_clear(self, event: Any) -> None:
        """Ctrl+C / Esc,C — copy selection, clear the input, or exit.

        The output buffer holds raw ANSI codes (e.g. muted tool-call
        detail); strip them so the clipboard gets plain text.
        """
        ui = self._ui
        buffer = event.app.current_buffer
        if buffer.selection_state:
            data = buffer.copy_selection()
            data.text = remove_style(data.text)
            if event.app.clipboard:
                event.app.clipboard.set_data(data)
            buffer.exit_selection()
            return
        if buffer.text.strip() != "":
            buffer.reset()
            return
        # No flush: the app is exiting.
        ui.cancel_pending_confirmations(flush=False)
        if ui.running_llm_task and not ui.running_llm_task.done():
            ui.running_llm_task.cancel()
            ui.append_to_output("\n<Esc> Canceled")
        # Abort a voice recording/download so exit does not wait on it.
        voice = getattr(ui, "voice", None)
        voice_task = None if voice is None else voice.task
        if voice_task is not None and not voice_task.done():
            voice_task.cancel()
        ui.execute_hook(
            HookEvent.STOP,
            {"reason": "ctrl_c", "session": ui.conversation_session_name},
        )
        event.app.exit()

    def _on_exit_if_empty(self, event: Any) -> None:
        """Ctrl+D — exit when the input buffer is empty."""
        ui = self._ui
        if event.app.current_buffer.text == "":
            ui.cancel_pending_confirmations(flush=False)
            if ui.running_llm_task and not ui.running_llm_task.done():
                ui.running_llm_task.cancel()
            event.app.exit()

    async def _on_clipboard_paste(self, clipboard: Any) -> None:
        """Paste an image from the clipboard, or fall back to text."""
        # lazy: tests patch `zrb.llm.util.clipboard.get_clipboard_image`
        # at the source path; hoisting would bind the name at
        # module-load and bypass the mock.
        from zrb.llm.util.clipboard import (
            get_clipboard_image,
            missing_tool_hint,
        )

        ui = self._ui
        img_bytes = await get_clipboard_image()
        if img_bytes is not None:
            # lazy: zrb internal (heavy via transitive)
            from zrb.llm.agent.types import BinaryContent

            scaled = scale_image_bytes(img_bytes, media_type="image/png")
            attachment = BinaryContent(data=scaled.data, media_type=scaled.media_type)
            ui.pending_attachments.append(attachment)
            size_kb = scaled.final_bytes / 1024
            if scaled.scaled:
                saved_kb = scaled.saved_bytes / 1024
                msg = (
                    f"\n  📸 Image pasted from clipboard ({size_kb:.1f} KB, "
                    f"scaled — saved {saved_kb:.1f} KB)\n"
                )
            else:
                msg = f"\n  📸 Image pasted from clipboard ({size_kb:.1f} KB)\n"
            ui.append_to_output(stylize_muted(msg))
            ui.invalidate_ui()
        else:
            hint = missing_tool_hint()
            if hint:
                ui.append_to_output(
                    stylize_error(f"\n  ❌ No image in clipboard.\n{hint}")
                )
                ui.invalidate_ui()
            elif clipboard:
                # Target input_field: focus may be on the read-only output pane.
                # lazy: heavy third-party
                from prompt_toolkit.application import get_app as _get_app

                _get_app().layout.focus(ui.input_field)
                ui.input_field.buffer.paste_clipboard_data(clipboard.get_data())

    def _on_escape(self, event: Any) -> None:
        ui = self._ui
        ui.cancel_pending_confirmations()
        # In agent view, Esc cancels the sub-agent's work only; Left leaves
        # the view and the main task is untouched.
        if getattr(ui, "viewing_agent_id", None) is not None:
            ui.cancel_viewed_agent()
            return
        if ui.running_llm_task and not ui.running_llm_task.done():
            ui.running_llm_task.cancel()
            ui.execute_hook(
                HookEvent.STOP,
                {
                    "reason": "escape",
                    "session": ui.conversation_session_name,
                },
            )
            ui.append_to_output("\n<Esc> Canceled")

    def _on_enter(self, event: Any, llm_task: "AnyTask") -> None:
        ui = self._ui
        # With focus on the output pane, current_buffer is the transcript;
        # submitting it would send the whole pane as input. Refocus instead.
        if not event.app.layout.has_focus(ui.input_field):
            event.app.layout.focus(ui.input_field)
            return

        if self._handle_multiline(event):
            return

        if ui.handle_confirmation(event):
            return

        # A queued message recalled with Up is edited in place, not resubmitted.
        if ui.handle_enter_queued_edit(event):
            return

        self._handle_enter_dispatch(event, llm_task)

    def _on_cycle_mode(self, event: Any) -> None:
        self._ui.cycle_mode()

    def _on_voice_ptt(self, event: Any) -> None:
        """Push-to-talk press: start/stop a voice recording.

        OS key-repeat is debounced; the engine is created once and cached.
        """
        ui = self._ui
        if not event.app.layout.has_focus(ui.input_field):
            ui.input_field.buffer.insert_text(" ")
            return

        now = time.time()
        if now - self._voice_last_press < self._KEY_REPEAT_DEBOUNCE:
            self._voice_last_press = now
            return
        self._voice_last_press = now

        if ui.voice.recording_active:
            ui.voice.recording_active = False
            if ui.voice.stop_event is not None:
                ui.voice.stop_event.set()
            ui.voice.mode_active = False
            ui.append_to_output(stylize_muted("  🎤 Stopped\n"))
            ui.invalidate_ui()
            return

        # lazy: heavy third-party — voice engine imports sounddevice/numpy
        from zrb.llm.voice import VoiceEngine

        if self._voice_engine is None:
            self._voice_engine = VoiceEngine()
        engine = self._voice_engine

        # Set before create_task so a key-repeat cannot race the new task.
        ui.voice.recording_active = True
        ui.voice.stop_event = asyncio.Event()
        ui.voice.task = None

        task = asyncio.create_task(self._voice_record_and_insert(engine))
        ui.voice.task = task
        ui.background_tasks.add(task)
        task.add_done_callback(ui.background_tasks.discard)

    async def _voice_record_and_insert(self, engine: "Any") -> None:
        """Record speech, then insert the transcription into the input field."""
        ui = self._ui
        # First use downloads the Vosk model (cancellable: /q and Ctrl+C
        # cancel this task). A pre-downloaded model must be extracted.
        if (
            not engine.is_ready
            and CFG.LLM_VOICE_MODE.strip().lower() == "vosk"
            and not engine.is_vosk_model_ready()
        ):
            ui.append_to_output(stylize_muted("\n  🎤 Downloading voice model..."))
            ui.invalidate_ui()
            try:
                await engine.download_vosk_model()
            except Exception as exc:
                self._end_voice_with_error(exc)
                return
            ui.append_to_output(stylize_muted("\n  🎤 Voice model ready"))
            ui.invalidate_ui()

        ui.append_to_output(stylize_muted("\n  🎤 Recording... "))
        ui.invalidate_ui()
        try:
            text = await engine.start_listening(
                stop_event=ui.voice.stop_event,
            )
        except Exception as exc:
            self._end_voice_with_error(exc)
            return
        self._reset_voice_state()
        if text:
            ui.input_field.buffer.insert_text(text)
            word_count = len(text.split())
            ui.append_to_output(
                stylize_muted(f"\n  🎤 Transcribed ({word_count} words)\n")
            )
        else:
            ui.append_to_output(stylize_muted("\n  🎤 No speech detected\n"))
        ui.invalidate_ui()

    def _end_voice_with_error(self, exc: Exception) -> None:
        self._reset_voice_state()
        self._ui.append_to_output(stylize_muted(f"\n  ⚠️ Voice error: {exc}\n"))
        self._ui.invalidate_ui()

    def _reset_voice_state(self) -> None:
        voice = self._ui.voice
        voice.mode_active = False
        voice.recording_active = False
        voice.task = None
        voice.stop_event = None

    def _handle_multiline(self, event) -> bool:
        """A trailing backslash with the cursor at the end becomes a newline."""
        buff = event.current_buffer
        text = buff.text
        if buff.cursor_position != len(text) or not text.endswith("\\"):
            return False
        buff.delete_before_cursor(count=1)
        buff.insert_text("\n")
        return True

    def _handle_enter_dispatch(self, event: Any, llm_task: "AnyTask") -> None:
        """Route submitted text to a sub-agent, a command, or the LLM."""
        ui = self._ui
        buff = event.current_buffer
        text = buff.text
        if not text.strip():
            return

        # In agent view every Enter is a message to the sub-agent, never a command.
        viewing_agent_id = getattr(ui, "viewing_agent_id", None)
        if viewing_agent_id is not None:
            session_id = get_session_ownership_key(ui.conversation_session_name)
            agent_id = viewing_agent_id
            message = text
            buff.reset()

            async def _send_to_sub_agent():
                # lazy: transitively heavy via internal — live_session.py
                # imports run_agent (zrb.llm.agent.run.runner), which pulls
                # in pydantic_ai.
                from zrb.llm.agent.subagent.live_session import (
                    live_subagent_session_registry,
                )

                await live_subagent_session_registry.send_message(
                    session_id, agent_id, message
                )
                # Echo into the sub-agent's buffer so its live view reads as a chat.
                entry = live_subagent_session_registry.get(session_id, agent_id)
                if entry is not None:
                    entry.buffered_ui.append_to_output(f"\n💬 {message.strip()}\n")

            task = asyncio.create_task(_send_to_sub_agent())
            ui.background_tasks.add(task)
            task.add_done_callback(ui.background_tasks.discard)
            return

        # Classify by recognition, not "/" prefix: command tokens are
        # user-configurable (e.g. ">" for redirect).
        kind = ui.classify_input(text)

        # /btw and the YOLO toggle run unguarded, even mid-response.
        if kind == "thinking_command":
            buff.reset()
            ui.schedule_command(text, guarded=False)
            return

        # Other commands mutate session state, so they wait out a response;
        # the buffer is kept for resubmission.
        if kind == "command":
            if ui.is_thinking:
                return
            buff.reset()
            ui.schedule_command(text)
            return

        # A plain message submitted mid-response is queued for the next turn.
        buff.append_to_history()
        ui.submit_user_message(llm_task, text)
        buff.reset()
