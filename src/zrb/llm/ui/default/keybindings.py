"""Key bindings for the default `UI`.

`setup_app_keybindings` wires the prompt-toolkit handlers; it stays one
method because each handler is a closure capturing `self` and the event
object. The dispatch logic for Enter — which routes through the slash
command handlers on `BaseUICommands` — is the bulk of the file.
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

    def __init__(self, ui: "UI") -> None:
        self._ui = ui

    def setup_app_keybindings(
        self, app_keybindings: "KeyBindings", llm_task: "AnyTask"
    ):
        # lazy: heavy third-party
        from prompt_toolkit.filters import Condition, has_completions

        ui = self._ui

        # While the AskUserQuestion selection widget is active it owns Enter and
        # newline keys (its own control bindings handle them); suppress the
        # app-level handlers so they don't double-fire / resolve with stale text.
        no_active_choice = Condition(
            lambda: not getattr(ui, "has_active_choice", lambda: False)()
        )

        # While the output pane shows a sub-agent's live view, Left returns to
        # the main session (navigation, never cancels the sub-agent's work).
        viewing_sub_agent = Condition(
            lambda: getattr(ui, "viewing_agent_id", None) is not None
        )

        # Ctrl+K toggles focus between the input and output panes. The
        # input/output controls bind no Tab/Shift+Tab focus traversal of their
        # own (see app/layout.py, app/keybinding.py), leaving Shift+Tab free to
        # cycle modes (below). Note: on Termux, Tab and Shift+Tab both produce byte
        # 0x09, so mode cycling via Shift+Tab is unavailable there.
        @app_keybindings.add("c-k")
        def _(event):
            if event.app.layout.has_focus(ui.input_field):
                event.app.layout.focus(ui.output_field)
            else:
                event.app.layout.focus(ui.input_field)

        @app_keybindings.add("c-c")
        @app_keybindings.add("escape", "c")
        def _(event):
            buffer = event.app.current_buffer
            if buffer.selection_state:
                data = buffer.copy_selection()
                # The output buffer holds raw ANSI codes (e.g. muted tool-call
                # detail); strip them so the clipboard gets plain text.
                data.text = remove_style(data.text)
                if event.app.clipboard:
                    event.app.clipboard.set_data(data)
                buffer.exit_selection()
                return
            if buffer.text.strip() != "":
                buffer.reset()
                return
            # Don't flush the confirmation buffer: the app is exiting, so
            # writing buffered tokens is wasted work and adds latency.
            ui.cancel_pending_confirmations(flush=False)
            if ui.running_llm_task and not ui.running_llm_task.done():
                ui.running_llm_task.cancel()
                ui.append_to_output("\n<Esc> Canceled")
            # Abort an in-flight voice recording/model-download so Ctrl+C
            # exits promptly instead of waiting on the download thread.
            voice_task = getattr(ui, "voice_task", None)
            if voice_task is not None and not voice_task.done():
                voice_task.cancel()
            ui.execute_hook(
                HookEvent.STOP,
                {"reason": "ctrl_c", "session": ui.conversation_session_name},
            )
            event.app.exit()

        @app_keybindings.add("c-d")
        def _(event):
            if event.app.current_buffer.text == "":
                ui.cancel_pending_confirmations(flush=False)
                if ui.running_llm_task and not ui.running_llm_task.done():
                    ui.running_llm_task.cancel()
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

                img_bytes = await get_clipboard_image()
                if img_bytes is not None:
                    # lazy: heavy third-party
                    from pydantic_ai import BinaryContent

                    scaled = scale_image_bytes(img_bytes, media_type="image/png")
                    attachment = BinaryContent(
                        data=scaled.data, media_type=scaled.media_type
                    )
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
                        # No image found — paste text into input field. Always
                        # target input_field, not current_buffer, since focus
                        # may be on the read-only output field.
                        # lazy: heavy third-party
                        from prompt_toolkit.application import get_app as _get_app

                        _get_app().layout.focus(ui.input_field)
                        ui.input_field.buffer.paste_clipboard_data(clipboard.get_data())

            task = asyncio.create_task(_handle_paste())
            ui.background_tasks.add(task)
            task.add_done_callback(ui.background_tasks.discard)

        @app_keybindings.add("escape")
        def _(event):
            # While viewing a sub-agent, Esc cancels what the sub-agent is
            # doing (mirroring the main agent's Esc) — it never leaves the
            # view (Left does that) and never touches the main task.
            if getattr(ui, "viewing_agent_id", None) is not None:
                ui.cancel_pending_confirmations()
                ui.cancel_viewed_agent()
                return
            ui.cancel_pending_confirmations()
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

        @app_keybindings.add("left", filter=viewing_sub_agent)
        def _(event):
            # Left while the output pane shows a sub-agent returns to the main
            # session. Filtered so Left still moves the text cursor in the
            # input field everywhere else (the app-level binding only matches
            # while `_viewing_agent_id` is set).
            ui.exit_agent_view()

        @app_keybindings.add("enter", filter=no_active_choice)
        def _(event):
            # Enter only ever acts on the input field. With focus on the
            # read-only output pane (Ctrl+K), event.current_buffer is the output
            # buffer — resolving a confirmation or submitting from it would send
            # the entire pane content (banner, help, transcript) as user input.
            # Refocus the input field instead.
            if not event.app.layout.has_focus(ui.input_field):
                event.app.layout.focus(ui.input_field)
                return

            if self._handle_multiline(event):
                return

            if ui.handle_confirmation(event):
                return

            # A still-queued message recalled into the input field (Up arrow)
            # is edited in place here instead of submitted as a new message.
            if ui.handle_enter_queued_edit(event):
                return

            self._handle_enter_dispatch(event, llm_task)

        @app_keybindings.add("c-y")
        def _(event):
            ui.toggle_yolo()

        # Ctrl+O expands/collapses the collapsible block at (or just before)
        # the output cursor — a tool call's truncated args, a hidden tool
        # result, or a thinking block collapsed once the model moved on.
        # Follows the tail by default, so with no scrolling this toggles the
        # most recently printed block. Unconditional (unlike `left` above):
        # `ui.toggle_collapsible_block` itself routes to the currently-viewed
        # sub-agent's own toggle-block scope when `viewing_agent_id` is set,
        # so this single binding is always correct regardless of what the
        # output pane is currently showing.
        @app_keybindings.add("c-o")
        def _(event):
            ui.toggle_collapsible_block()

        if CFG.IS_TERMUX:
            # On Termux, Tab and Shift+Tab are indistinguishable (both byte 0x09),
            # so Shift+Tab never arrives — bind plain Tab to mode cycling there.
            @app_keybindings.add("tab", filter=no_active_choice & ~has_completions)
            def _(event):
                ui.cycle_mode()

        else:
            # Shift+Tab — cycle normal → accept-edits → plan. Gated so a completion
            # menu keeps Shift+Tab for previous-completion, and a choice widget keeps
            # its own back-tab navigation.
            @app_keybindings.add("s-tab", filter=no_active_choice & ~has_completions)
            def _(event):
                ui.cycle_mode()

        @app_keybindings.add("c-j", filter=no_active_choice)  # Ctrl+J / Ctrl+Enter
        @app_keybindings.add("c-space", filter=no_active_choice)  # Ctrl+Space fallback
        def _(event):
            event.current_buffer.insert_text("\n")

        # Voice push-to-talk: press to record, press again to stop.
        #
        # Terminals cannot detect key-release (byte 0x20 for space is sent on
        # key-down only), so Claude Code's hold-to-talk model is unavailable.
        # Instead: press once → start recording; press again → stop + exit
        # voice mode. Transcribed text appears in the input field for editing,
        # then the user presses Enter to submit like a normal message.
        # OS key-repeat is filtered via a 300ms debounce (macOS default repeat
        # interval is ~67ms). Ctrl+Space always inserts a literal newline.
        voice_ptt_key = CFG.LLM_VOICE_PUSH_TO_TALK_KEY.strip().lower()
        voice_mode_active = Condition(lambda: getattr(ui, "voice_mode_active", False))
        _last_press: float = 0.0
        _KEY_REPEAT_DEBOUNCE = 0.3

        # Cache the engine across presses so the transcriber backend is
        # resolved only once (lazy import on first use).
        _voice_engine: "Any | None" = None

        @app_keybindings.add(voice_ptt_key, filter=voice_mode_active & no_active_choice)
        def _(event):
            nonlocal _voice_engine, _last_press

            if not event.app.layout.has_focus(ui.input_field):
                ui.input_field.buffer.insert_text(" ")
                return

            # Debounce: filter OS key-repeat (events <300ms apart).
            now = time.time()
            if now - _last_press < _KEY_REPEAT_DEBOUNCE:
                _last_press = now
                return
            _last_press = now

            # Second press while recording → signal stop, exit voice mode.
            if ui.voice_recording_active:
                ui.voice_recording_active = False
                if ui.voice_stop_event is not None:
                    ui.voice_stop_event.set()
                ui.voice_mode_active = False
                ui.append_to_output(stylize_muted("  🎤 Stopped\n"))
                ui.invalidate_ui()
                return

            # lazy: heavy third-party — voice engine imports sounddevice/numpy
            from zrb.llm.voice import VoiceEngine  # noqa: F811

            if _voice_engine is None:
                _voice_engine = VoiceEngine()
            engine = _voice_engine

            # Set synchronously BEFORE create_task so key-repeat can't race.
            ui.voice_recording_active = True
            ui.voice_stop_event = asyncio.Event()
            ui.voice_task = None

            async def record_and_insert():
                # Download the Vosk model before recording (first use only).
                # This keeps the "Downloading..." status visible. The download
                # is chunked and cancellable, so /q or Ctrl+C aborts it (both
                # cancel this task). A pre-downloaded model must be extracted
                # (the bare .zip is not detected). After the first download the
                # model is cached for future recordings.
                if not engine.is_ready and CFG.LLM_VOICE_MODE.strip().lower() == "vosk":
                    if not engine.is_vosk_model_ready():
                        ui.append_to_output(
                            stylize_muted("\n  🎤 Downloading voice model...")
                        )
                        ui.invalidate_ui()
                        try:
                            await engine.download_vosk_model()
                        except Exception as exc:
                            ui.voice_mode_active = False
                            ui.voice_recording_active = False
                            ui.voice_task = None
                            ui.voice_stop_event = None
                            ui.append_to_output(
                                stylize_muted(f"\n  ⚠️ Voice error: {exc}\n")
                            )
                            ui.invalidate_ui()
                            return
                        ui.append_to_output(stylize_muted("\n  🎤 Voice model ready"))
                        ui.invalidate_ui()

                ui.append_to_output(stylize_muted("\n  🎤 Recording... "))
                ui.invalidate_ui()
                try:
                    text = await engine.start_listening(
                        stop_event=ui.voice_stop_event,
                    )
                except Exception as exc:
                    ui.voice_mode_active = False
                    ui.voice_recording_active = False
                    ui.voice_task = None
                    ui.voice_stop_event = None
                    ui.append_to_output(stylize_muted(f"\n  ⚠️ Voice error: {exc}\n"))
                    ui.invalidate_ui()
                    return
                ui.voice_mode_active = False
                ui.voice_recording_active = False
                ui.voice_task = None
                ui.voice_stop_event = None
                if text:
                    ui.input_field.buffer.insert_text(text)
                    word_count = len(text.split())
                    ui.append_to_output(
                        stylize_muted(f"\n  🎤 Transcribed ({word_count} words)\n")
                    )
                else:
                    ui.append_to_output(stylize_muted("\n  🎤 No speech detected\n"))
                ui.invalidate_ui()

            task = asyncio.create_task(record_and_insert())
            ui.voice_task = task
            ui.background_tasks.add(task)
            task.add_done_callback(ui.background_tasks.discard)

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

    def _handle_enter_dispatch(self, event: Any, llm_task: "AnyTask") -> None:
        """Split out of the Enter closure to keep `setup_app_keybindings` under
        the complexity ratchet."""
        ui = self._ui
        buff = event.current_buffer
        text = buff.text
        if not text.strip():
            return

        # While viewing a sub-agent every Enter is a message to it — never a
        # /command for the main session.
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
                # Echo the user's message into the sub-agent's own buffer so
                # its live view reads as a conversation.
                entry = live_subagent_session_registry.get(session_id, agent_id)
                if entry is not None:
                    entry.buffered_ui.append_to_output(f"\n💬 {message.strip()}\n")

            task = asyncio.create_task(_send_to_sub_agent())
            ui.background_tasks.add(task)
            task.add_done_callback(ui.background_tasks.discard)
            return

        # Route by recognition, not by "/" prefix — command tokens are
        # user-configurable (e.g. ">" for redirect). Recognized commands go
        # through the hook-wrapped async dispatch (PreCommand may block;
        # PostCommand fires after); plain text is sent to the LLM.
        kind = ui.classify_input(text)

        # Run-while-thinking commands (/btw, YOLO toggle) dispatch even while
        # the LLM is responding.
        if kind == "thinking_command":
            # Not guarded: like main, /btw and YOLO toggle run independently
            # — never blocked by, nor blocking, another in-flight command.
            buff.reset()
            ui.schedule_command(text, guarded=False)
            return

        # Commands stay gated while thinking: they mutate session/UI state
        # (/save, /load, /model), so running one mid-response is unsafe. The
        # buffer is kept so the user can resubmit once the response finishes.
        if kind == "command":
            if ui.is_thinking:
                return
            buff.reset()
            ui.schedule_command(text)
            return

        # Plain message — record for up-arrow recall, then submit. Submitting
        # while thinking is allowed: the message loop runs one job at a time,
        # so it lands in the queue and runs when the current turn ends.
        buff.append_to_history()
        ui.submit_user_message(llm_task, text)
        buff.reset()
