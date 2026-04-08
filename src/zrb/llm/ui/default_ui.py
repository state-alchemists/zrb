from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from collections.abc import AsyncIterable, Callable
from typing import TYPE_CHECKING, Any, TextIO

from zrb.context.any_context import AnyContext
from zrb.llm.app.keybinding import create_output_keybindings
from zrb.llm.app.layout import create_input_field, create_layout, create_output_field
from zrb.llm.app.redirection import GlobalStreamCapture
from zrb.llm.app.style import create_style
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.hook.interface import HookEvent
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.tool_call import (
    ArgumentFormatter,
    ResponseHandler,
    ToolPolicy,
)
from zrb.llm.ui.base_ui import BaseUI
from zrb.task.any_task import AnyTask
from zrb.util.ascii_art.banner import create_banner
from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from prompt_toolkit import Application
    from prompt_toolkit.document import Document
    from prompt_toolkit.formatted_text import AnyFormattedText
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.styles import Style
    from pydantic_ai import UserContent
    from pydantic_ai.models import Model
    from rich.theme import Theme

logger = logging.getLogger(__name__)


class UI(BaseUI):
    def __init__(
        self,
        ctx: AnyContext,
        yolo_xcom_key: str,
        greeting: str,
        assistant_name: str,
        ascii_art: str,
        jargon: str,
        output_lexer: Lexer,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        initial_message: Any = "",
        initial_attachments: list["UserContent"] = [],
        conversation_session_name: str = "",
        is_yolo: bool | frozenset = False,
        triggers: list[Callable[[], AsyncIterable[Any]]] = [],
        response_handlers: list[ResponseHandler] = [],
        tool_policies: list[ToolPolicy] = [],
        argument_formatters: list[ArgumentFormatter] = [],
        markdown_theme: "Theme | None" = None,
        summarize_commands: list[str] = [],
        attach_commands: list[str] = [],
        exit_commands: list[str] = [],
        info_commands: list[str] = [],
        save_commands: list[str] = [],
        load_commands: list[str] = [],
        redirect_output_commands: list[str] = [],
        yolo_toggle_commands: list[str] = [],
        set_model_commands: list[str] = [],
        exec_commands: list[str] = [],
        btw_commands: list[str] = [],
        custom_commands: list[AnyCustomCommand] = [],
        model: "Model | str | None" = None,
        custom_model_names: list[str] = [],
    ):
        super().__init__(
            ctx=ctx,
            yolo_xcom_key=yolo_xcom_key,
            assistant_name=assistant_name,
            llm_task=llm_task,
            history_manager=history_manager,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            conversation_session_name=conversation_session_name,
            is_yolo=is_yolo,
            triggers=triggers,
            response_handlers=response_handlers,
            tool_policies=tool_policies,
            argument_formatters=argument_formatters,
            markdown_theme=markdown_theme,
            summarize_commands=summarize_commands,
            attach_commands=attach_commands,
            exit_commands=exit_commands,
            info_commands=info_commands,
            save_commands=save_commands,
            load_commands=load_commands,
            redirect_output_commands=redirect_output_commands,
            yolo_toggle_commands=yolo_toggle_commands,
            set_model_commands=set_model_commands,
            exec_commands=exec_commands,
            btw_commands=btw_commands,
            custom_commands=custom_commands,
            model=model,
        )
        self._ascii_art = ascii_art
        self._jargon = jargon

        self._refresh_task: asyncio.Task | None = None

        # Output Capture
        self._capture = GlobalStreamCapture(self.append_to_output)
        # UI Styles
        self._style = create_style()
        # Input Area
        from prompt_toolkit.history import InMemoryHistory

        self._input_history = InMemoryHistory()
        self._input_field = create_input_field(
            history_manager=self._history_manager,
            attach_commands=self._attach_commands,
            exit_commands=self._exit_commands,
            info_commands=self._info_commands,
            save_commands=self._save_commands,
            load_commands=self._load_commands,
            redirect_output_commands=self._redirect_output_commands,
            summarize_commands=self._summarize_commands,
            set_model_commands=self._set_model_commands,
            exec_commands=self._exec_commands,
            custom_commands=self._custom_commands,
            history=self._input_history,
            custom_model_names=custom_model_names,
        )
        # Output Area (Read-only chat history)
        help_text = self._get_help_text(limit=25)
        full_greeting = create_banner(self._ascii_art, f"{greeting}\n{help_text}")
        custom_output_kb = create_output_keybindings(self._input_field)
        self._output_field = create_output_field(
            full_greeting, output_lexer, key_bindings=custom_output_kb
        )
        from prompt_toolkit.layout import Layout

        self._layout = create_layout(
            title=self._assistant_name,
            jargon=self._jargon,
            input_field=self._input_field,
            output_field=self._output_field,
            info_bar_text=self._get_info_bar_text,
            status_bar_text=self._get_status_bar_text,
        )
        # Key Bindings
        from prompt_toolkit.key_binding import KeyBindings

        self._app_kb = KeyBindings()
        self._setup_app_keybindings(
            app_keybindings=self._app_kb, llm_task=self._llm_task
        )
        # Application
        self._application = self._create_application(
            layout=self._layout, keybindings=self._app_kb, style=self._style
        )
        # Send message if first_message is provided. Make sure only run at most once
        if self._initial_message:
            self._application.after_render.add_handler(self._on_first_render)

    async def run_async(self):
        """Run the application and manage triggers."""
        # Start triggers
        for trigger_fn in self._triggers:
            trigger_task = self._application.create_background_task(
                self._trigger_loop(trigger_fn)
            )
            self._trigger_tasks.append(trigger_task)

        # Start message processor
        self._process_messages_task = self._application.create_background_task(
            self._process_messages_loop()
        )
        # Add to background tasks to prevent premature garbage collection
        if hasattr(self, "_background_tasks"):
            self._background_tasks.add(self._process_messages_task)

        # Start system info update loop
        self._system_info_task = self._application.create_background_task(
            self._update_system_info_loop()
        )
        # Add to background tasks to prevent premature garbage collection
        if hasattr(self, "_background_tasks"):
            self._background_tasks.add(self._system_info_task)

        # Start refresh loop (fix for lagging/artifacts)
        self._refresh_task = self._application.create_background_task(
            self._refresh_loop()
        )
        # Add to background tasks to prevent premature garbage collection
        if hasattr(self, "_background_tasks"):
            self._background_tasks.add(self._refresh_task)

        try:
            self._capture.start()
            # Perform initial system info update
            await self._update_system_info()
            return await self._application.run_async()
        finally:
            self._capture.stop()
            # Print buffered output after UI closes
            buffered_output = self._capture.get_buffered_output()
            if buffered_output:
                print(buffered_output, end="")

            if self._process_messages_task:
                self._process_messages_task.cancel()
                try:
                    await self._process_messages_task
                except (asyncio.CancelledError, RuntimeError):
                    # Task was cancelled or event loop is closed
                    pass
                finally:
                    # Remove from background tasks
                    if hasattr(self, "_background_tasks"):
                        self._background_tasks.discard(self._process_messages_task)

            # Empty the queue
            while not self._message_queue.empty():
                try:
                    self._message_queue.get_nowait()
                    self._message_queue.task_done()
                except asyncio.QueueEmpty:
                    break

            # Stop triggers
            for trigger_task in self._trigger_tasks:
                trigger_task.cancel()
                try:
                    await trigger_task
                except (asyncio.CancelledError, RuntimeError):
                    pass
            self._trigger_tasks.clear()

            if self._system_info_task:
                self._system_info_task.cancel()
                try:
                    await self._system_info_task
                except (asyncio.CancelledError, RuntimeError):
                    pass
                finally:
                    # Remove from background tasks
                    if hasattr(self, "_background_tasks"):
                        self._background_tasks.discard(self._system_info_task)

            if self._refresh_task:
                self._refresh_task.cancel()
                try:
                    await self._refresh_task
                except (asyncio.CancelledError, RuntimeError):
                    pass
                finally:
                    # Remove from background tasks
                    if hasattr(self, "_background_tasks"):
                        self._background_tasks.discard(self._refresh_task)

    async def _refresh_loop(self):
        """Periodically invalidate UI to fix artifacts/lag."""
        from prompt_toolkit.application import get_app

        while True:
            try:
                app = get_app()
                app.invalidate()
                # If input is focused, ensure we keep showing the latest content.
                if app.layout.has_focus(self._input_field):
                    self._scroll_output_to_bottom()
            except Exception:
                pass
            try:
                await asyncio.sleep(5.0)
            except RuntimeError:
                # Event loop closed during shutdown
                break

    def _scroll_output_to_bottom(self):
        """Scroll output field to the bottom."""
        try:
            buffer = self._output_field.buffer
            if buffer.cursor_position != len(buffer.text):
                buffer.cursor_position = len(buffer.text)
        except Exception:
            pass

    def _on_first_render(self, app: Application):
        """Handle initial message (the message sent when creating the UI)"""
        self._application.after_render.remove_handler(self._on_first_render)
        self._submit_user_message(self._llm_task, self._initial_message)

    async def ask_user(self, prompt: str) -> str:
        """Prompts the user for input via the main input field, blocking until provided.

        This method queues confirmation requests to handle multiple concurrent callers
        (e.g., parallel delegate agents). Each caller waits for its turn in the queue.
        """
        from prompt_toolkit.application import get_app

        # Create a future for this confirmation request
        future: asyncio.Future[str] = asyncio.Future()

        # Add to queue with prompt
        self._confirmation_queue.append((future, prompt))

        # Check if we can become current immediately
        if self._current_confirmation is None:
            self._current_confirmation = future
            # Show the prompt only when we become current
            if prompt:
                self.append_to_output(prompt, end="")
            get_app().invalidate()
        # If there's already a current confirmation, this one waits in queue
        # (prompt will be shown when it becomes current)

        try:
            # Wait for the future to be resolved
            result = await future
            return result
        finally:
            # Remove this future from queue (in case of cancellation)
            self._confirmation_queue = [
                (f, p) for f, p in self._confirmation_queue if f is not future
            ]
            if self._current_confirmation is future:
                self._current_confirmation = None
                # Activate next confirmation in queue
                self._activate_next_confirmation()

    def _activate_next_confirmation(self):
        """Activate the next confirmation in the queue after one completes."""
        from prompt_toolkit.application import get_app

        # Remove completed futures
        self._confirmation_queue = [
            (f, p) for f, p in self._confirmation_queue if not f.done()
        ]

        if self._confirmation_queue and self._current_confirmation is None:
            # Activate the next one
            future, prompt = self._confirmation_queue[0]
            self._current_confirmation = future
            # Show the prompt for this confirmation
            if prompt:
                self.append_to_output(prompt, end="")
            get_app().invalidate()

    def _cancel_pending_confirmations(self):
        """Cancel all pending confirmation futures and clear the queue.

        This is called when the user presses Ctrl+C or Escape to ensure
        that any blocked ask_user() calls are properly released.
        """
        # Cancel all futures in the queue
        for future, _ in self._confirmation_queue:
            if not future.done():
                future.cancel()
        # Clear the queue
        self._confirmation_queue.clear()
        # Reset current confirmation
        self._current_confirmation = None

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        from prompt_toolkit.application import run_in_terminal

        def run_subprocess():
            # Run the command. Standard streams will inherit from the parent,
            # which have been restored to the TTY by self._capture.pause()
            subprocess.call(cmd, shell=shell)

        # Pause capture and await run_in_terminal.
        # It's crucial to await so the pause() context manager stays active
        # until the subprocess (e.g. vim) finishes.
        with self._capture.pause():
            await run_in_terminal(run_subprocess)

    def invalidate_ui(self):
        from prompt_toolkit.application import get_app

        try:
            get_app().invalidate()
        except Exception:
            pass

    def on_exit(self):
        from prompt_toolkit.application import get_app

        try:
            get_app().exit()
        except Exception:
            pass

        # Try to cancel any background tasks before exit
        if hasattr(self, "_background_tasks"):
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()

    @property
    def application(self) -> Application:
        return self._application

    def _create_application(
        self,
        layout: Layout,
        keybindings: KeyBindings,
        style: Style,
    ) -> Application:
        from prompt_toolkit import Application
        from prompt_toolkit.output import create_output

        try:
            from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard

            clipboard = PyperclipClipboard()
        except ImportError:
            # Fallback to in-memory clipboard if pyperclip is not available
            from prompt_toolkit.clipboard import InMemoryClipboard

            clipboard = InMemoryClipboard()
        except Exception:
            # Fallback to in-memory clipboard on any other error
            from prompt_toolkit.clipboard import InMemoryClipboard

            clipboard = InMemoryClipboard()

        output = create_output(stdout=self._capture.get_original_stdout())

        # Wrap output to make get_size more robust
        # This prevents crashes on Windows when the console is not correctly detected
        original_get_size = output.get_size

        def robust_get_size():
            try:
                return original_get_size()
            except Exception:
                from prompt_toolkit.data_structures import Size

                size = get_terminal_size()
                return Size(rows=size.lines, columns=size.columns)

        output.get_size = robust_get_size

        return Application(
            layout=layout,
            key_bindings=keybindings,
            style=style,
            full_screen=True,
            mouse_support=True,
            refresh_interval=0.5,
            output=output,
            clipboard=clipboard,
        )

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

        # 1. Construct lines
        line1_html = (
            f" 🤖 <b>Model:</b> {model_name} "
            f"| 💬 <b>Session:</b> {self._conversation_session_name} "
            f"| 🤠 <b>YOLO:</b> {yolo_text}"
        )
        line2_html = (
            f" 📂 <b>Dir:</b> {self._cwd} " f"| 🌿 <b>Git:</b> {self._git_info}"
        )

        # 2. Manual centering and clearing
        total_cols = get_terminal_size().columns

        def center_line(html_text: str) -> str:
            # Calculate visible width (fragment_list_width needs list of fragments)
            fragments = HTML(html_text).__pt_formatted_text__()
            visible_width = fragment_list_width(fragments)
            padding = max(0, (total_cols - visible_width) // 2)
            # Add padding to center, and more padding at end to clear entire line
            return (
                " " * padding + html_text + " " * (total_cols - visible_width - padding)
            )

        return HTML(center_line(line1_html) + "\n" + center_line(line2_html))

    def _get_status_bar_text(self) -> AnyFormattedText:
        if self._is_thinking:
            return [("class:thinking", f" ⏳ {self._assistant_name} is working... ")]
        return [("class:status", " 🚀 Ready ")]

    def _setup_app_keybindings(self, app_keybindings: KeyBindings, llm_task: AnyTask):
        @app_keybindings.add("f6")
        def _(event):
            # Toggle focus between input and output field
            if event.app.layout.has_focus(self._input_field):
                event.app.layout.focus(self._output_field)
            else:
                event.app.layout.focus(self._input_field)

        @app_keybindings.add("c-c")
        @app_keybindings.add("escape", "c")
        def _(event):
            # If text is selected, copy it instead of exiting
            buffer = event.app.current_buffer
            if buffer.selection_state:
                data = buffer.copy_selection()
                if event.app.clipboard:
                    event.app.clipboard.set_data(data)
                buffer.exit_selection()
                return
            # If buffer is not empty, clear it
            if buffer.text != "":
                buffer.reset()
                return
            # Cancel any pending confirmation futures
            self._cancel_pending_confirmations()
            # Cancel running task if any (similar to escape key)
            if self._running_llm_task and not self._running_llm_task.done():
                self._running_llm_task.cancel()
                self.append_to_output("\n<Esc> Canceled")
            # Hook: Stop
            self.execute_hook(
                HookEvent.STOP,
                {"reason": "ctrl_c", "session": self._conversation_session_name},
            )
            event.app.exit()

        @app_keybindings.add("c-v")
        @app_keybindings.add("escape", "v")
        def _(event):
            # Try image paste first; fall back to normal text paste.
            # We capture clipboard here before going async because
            # prompt_toolkit may recycle the event object.
            clipboard = event.app.clipboard

            async def _handle_paste():
                from zrb.llm.util.clipboard import (
                    get_clipboard_image,
                    missing_tool_hint,
                )
                from zrb.util.cli.style import stylize_error, stylize_faint

                img_bytes = await get_clipboard_image()
                if img_bytes is not None:
                    from pydantic_ai import BinaryContent

                    attachment = BinaryContent(data=img_bytes, media_type="image/png")
                    self._pending_attachments.append(attachment)
                    size_kb = len(img_bytes) / 1024
                    self.append_to_output(
                        stylize_faint(
                            f"\n  📸 Image pasted from clipboard ({size_kb:.1f} KB)\n"
                        )
                    )
                    self.invalidate_ui()
                else:
                    hint = missing_tool_hint()
                    if hint:
                        self.append_to_output(
                            stylize_error(f"\n  ❌ No image in clipboard.\n{hint}")
                        )
                        self.invalidate_ui()
                    elif clipboard:
                        # No image found — normal text paste into input field.
                        # Always target input_field, not current_buffer, since
                        # current focus may be the read-only output field.
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
            # Cancel any pending confirmation futures
            self._cancel_pending_confirmations()
            if self._running_llm_task and not self._running_llm_task.done():
                self._running_llm_task.cancel()
                # Hook: Stop
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
            # Handle multiline (trailing backslash)
            if self._handle_multiline(event):
                return

            # Handle confirmation (should work even when LLM is thinking)
            if self._handle_confirmation(event):
                return

            # Handle empty inputs
            buff = event.current_buffer
            text = buff.text
            if not text.strip():
                return

            # These commands work even while the LLM is thinking
            if self._handle_btw_command(text):
                buff.reset()
                return
            if self._handle_toggle_yolo(text):
                buff.reset()
                return

            # Prevent new messages when LLM is thinking
            if self._is_thinking:
                return

            # Handle other commands
            if self._handle_exit_command(text):
                return
            if self._handle_info_command(text):
                buff.reset()
                return
            if self._handle_save_command(text):
                buff.reset()
                return
            if self._handle_load_command(text):
                buff.reset()
                return
            if self._handle_redirect_command(text):
                buff.reset()
                return
            if self._handle_attach_command(text):
                buff.reset()
                return
            if self._handle_set_model_command(text):
                buff.reset()
                return
            if self._handle_exec_command(text):
                buff.reset()
                return
            if self._handle_custom_command(text):
                buff.reset()
                return

            # Append to history manually to ensure persistence
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
        # Check for multiline indicator (trailing backslash)
        if text.strip().endswith("\\"):
            # If cursor is at the end, remove backslash and insert newline
            if buff.cursor_position == len(text):
                # Remove the backslash (assuming it's the last char)
                # We need to be careful with whitespace after backslash if we used strip()
                # Let's just check the character before cursor
                if text.endswith("\\"):
                    buff.delete_before_cursor(count=1)
                    buff.insert_text("\n")
                    return True
        return False

    def _handle_confirmation(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        if self._current_confirmation is not None:
            # Echo the user input
            self.append_to_output(text + "\n")
            if not self._current_confirmation.done():
                self._current_confirmation.set_result(text)
            # Clear current and activate next
            self._current_confirmation = None
            self._activate_next_confirmation()
            buff.reset()
            return True
        return False

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

        # Helper to safely append to read-only buffer
        current_text = self._output_field.text

        # Determine if we should scroll to end.
        # We scroll to end if:
        # 1. We are focusing on the input field
        # 2. We are on the last line of the output
        is_input_focused = False
        try:
            # We use get_app() here as it is safer during initialization
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

        # Construct the new content, applying faint styling for non-text kinds
        content = sep.join([str(value) for value in values]) + end
        if kind != "text":
            from zrb.util.cli.style import stylize_faint

            content = stylize_faint(content)
        # Handle carriage returns (\r) for status updates
        if "\r" in content:
            # Find the start of the last line in the current text
            last_newline = current_text.rfind("\n")
            if last_newline == -1:
                previous = ""
                last = current_text
            else:
                previous = current_text[: last_newline + 1]
                last = current_text[last_newline + 1 :]
            combined = last + content
            # Remove content before \r on the same line
            # [^\n]* matches any character except newline
            resolved = re.sub(r"[^\n]*\r", "", combined)
            new_text = previous + resolved
        else:
            new_text = current_text + content

        # Hook: Notification
        # Use thread-safe executor instead of fire-and-forget
        try:
            # Schedule notification hook execution
            # The hook manager now uses thread pool executor
            self.execute_hook(
                HookEvent.NOTIFICATION,
                {"content": content, "session": self._conversation_session_name},
                session_id=self._conversation_session_name,
                cwd=self._cwd,
            )
        except Exception as e:
            logger.error(f"Failed to trigger notification hook: {e}")

        # Update content directly
        # We use bypass_readonly=True by constructing a Document
        new_cursor_position = (
            len(new_text)
            if should_scroll_to_end
            else self._output_field.buffer.cursor_position
        )
        # Ensure cursor position is valid (within bounds)
        new_cursor_position = min(max(0, new_cursor_position), len(new_text))

        self._output_field.buffer.set_document(
            Document(new_text, cursor_position=new_cursor_position),
            bypass_readonly=True,
        )
        self.invalidate_ui()

    def _get_output_field_width(self) -> int | None:
        try:
            width = get_terminal_size().columns - 4
            if width < 10:
                width = None
        except Exception:
            width = None
        return width
