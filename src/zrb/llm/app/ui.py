import asyncio
import contextlib
import io
import re
import string
import sys
from collections.abc import Callable
from datetime import datetime
from typing import Any, TextIO

from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML, AnyFormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window, WindowAlign
from prompt_toolkit.layout.containers import Float, FloatContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from zrb.context.shared_context import SharedContext
from zrb.llm.app.completion import InputCompleter
from zrb.llm.app.confirmation.handler import (
    ConfirmationHandler,
    ConfirmationMiddleware,
    last_confirmation,
)
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.util.string.name import get_random_name

EXIT_COMMANDS = ["/q", "/bye", "/quit", "/exit"]


class StdoutToUI(io.TextIOBase):
    """Redirect stdout to UI's append_to_output."""

    def __init__(self, ui_callback):
        self.ui_callback = ui_callback
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self._is_first_write = True

    def write(self, text: str) -> int:
        text = text.expandtabs(4)
        if text:
            if self._is_first_write:
                self.ui_callback("\n", end="")
                self._is_first_write = False
            self.ui_callback(text, end="")
            get_app().invalidate()
        return len(text)

    def flush(self):
        self.original_stdout.flush()
        self.original_stderr.flush()


class UI:
    def __init__(
        self,
        greeting: str,
        assistant_name: str,
        jargon: str,
        output_lexer: Lexer,
        llm_task: AnyTask,
        initial_message: Any = "",
        initial_attachments: list[str] = [],
        conversation_session_name: str = "",
        yolo: bool = False,
        triggers: list[Callable[[], Any]] = [],
        confirmation_middlewares: list[ConfirmationMiddleware] = [],
    ):
        self._is_thinking = False
        self._running_llm_task: asyncio.Task | None = None
        self._llm_task = llm_task
        self._assistant_name = assistant_name
        self._jargon = jargon
        self._initial_message = initial_message
        self._conversation_session_name = conversation_session_name
        if not self._conversation_session_name:
            self._conversation_session_name = get_random_name()
        self._yolo = yolo
        self._triggers = triggers
        self._trigger_tasks: list[asyncio.Task] = []
        # Attachments
        self._pending_attachments: list[str] = list(initial_attachments)
        # Confirmation Handler
        self._confirmation_handler = ConfirmationHandler(
            middlewares=confirmation_middlewares + [last_confirmation]
        )
        # Confirmation state (Used by ask_user and keybindings)
        self._waiting_for_confirmation = False
        self._confirmation_future: asyncio.Future[str] | None = None
        # UI Styles
        self._style = self._create_style()
        # Input Area
        self._input_field = self._create_input_field()
        # Output Area (Read-only chat history)
        self._output_field = self._create_output_field(greeting, output_lexer)
        self._output_field.control.key_bindings = self._create_output_keybindings(
            self._input_field
        )
        self._layout = self._create_layout(
            title=self._assistant_name,
            jargon=self._jargon,
            input_field=self._input_field,
            output_field=self._output_field,
            status_bar_text=self._get_status_bar_text,
        )
        # Key Bindings
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

        try:
            with patch_stdout():
                return await self._application.run_async()
        finally:
            # Stop triggers
            for trigger_task in self._trigger_tasks:
                trigger_task.cancel()
            self._trigger_tasks.clear()

    async def _trigger_loop(self, trigger_fn: Callable[[], Any]):
        while True:
            try:
                if asyncio.iscoroutinefunction(trigger_fn):
                    result = await trigger_fn()
                else:
                    result = await asyncio.to_thread(trigger_fn)

                if result:
                    self._submit_user_message(self._llm_task, str(result))

            except asyncio.CancelledError:
                break
            except Exception:
                # Keep running on error, maybe log it
                pass

    def _on_first_render(self, app: Application):
        self._application.after_render.remove_handler(self._on_first_render)
        self._submit_user_message(self._llm_task, self._initial_message)

    async def ask_user(self, prompt: str) -> str:
        """Prompts the user for input via the main input field, blocking until provided."""
        self._waiting_for_confirmation = True
        self._confirmation_future = asyncio.Future()

        if prompt:
            self.append_to_output(prompt, end="")

        get_app().invalidate()

        try:
            return await self._confirmation_future
        finally:
            self._waiting_for_confirmation = False
            self._confirmation_future = None

    async def _confirm_tool_execution(self, call: Any) -> Any:
        return await self._confirmation_handler.handle(self, call)

    @property
    def triggers(self) -> list[Callable[[], Any]]:
        return self._triggers

    @triggers.setter
    def triggers(self, value: list[Callable[[], Any]]):
        self._triggers = value

    @property
    def application(self) -> Application:
        return self._application

    def _create_style(self) -> Style:
        return Style.from_dict(
            {
                "frame.label": "bg:#000000 #ffff00",
                "thinking": "ansigreen italic",
                "faint": "#888888",
                "output_field": "bg:#000000 #eeeeee", 
                "input_field": "bg:#000000 #eeeeee", 
                "text": "#eeeeee",
                "status": "reverse",
                "bottom-toolbar": "bg:#333333 #aaaaaa",
            }
        )

    def _create_output_field(self, greeting: str, lexer: Lexer) -> TextArea:
        return TextArea(
            text=greeting.rstrip() + "\n\n",
            read_only=True,
            scrollbar=False,
            wrap_lines=True,
            lexer=lexer,
            focus_on_click=True,
            focusable=True,
            style="class:output_field"
        )

    def _create_input_field(self) -> TextArea:
        summarize_commands = getattr(self._llm_task, "_summarize_command", [])
        all_commands = EXIT_COMMANDS + ["/attach"] + summarize_commands
        return TextArea(
            height=4,
            prompt=HTML('<style color="ansibrightblue"><b>&gt;&gt;&gt; </b></style>'),
            multiline=True,
            wrap_lines=True,
            completer=InputCompleter(all_commands),
            complete_while_typing=True,
            focus_on_click=True,
            style="class:input_field"
        )

    def _create_application(
        self,
        layout: Layout,
        keybindings: KeyBindings,
        style: Style,
    ) -> Application:
        return Application(
            layout=layout,
            key_bindings=keybindings,
            style=style,
            full_screen=True,
            mouse_support=True,
        )

    def _create_layout(
        self,
        title: str,
        jargon: str,
        input_field: TextArea,
        output_field: TextArea,
        status_bar_text: AnyFormattedText,
    ) -> Layout:
        title_bar_text = HTML(
            f" <style bg='ansipurple' color='white'><b> {title} </b></style> "
            f"<style color='#888888'>| {jargon}</style>"
        )
        return Layout(
            FloatContainer(
                content=HSplit(
                    [
                        # Title Bar
                        Window(
                            height=2,
                            content=FormattedTextControl(title_bar_text),
                            style="class:title-bar",
                            align=WindowAlign.CENTER,
                        ),
                        # Chat History
                        Frame(output_field, title="Conversation", style="class:frame"),
                        # Input Area
                        Frame(
                            input_field,
                            title="(ENTER to send, CTRL+ENTER for newline, ESC to cancel)",
                            style="class:input-frame",
                        ),
                        # Status Bar
                        Window(
                            height=1,
                            content=FormattedTextControl(status_bar_text),
                            style="class:bottom-toolbar",
                        ),
                    ]
                ),
                floats=[
                    Float(
                        xcursor=True,
                        ycursor=True,
                        content=CompletionsMenu(max_height=16, scroll_offset=1),
                    ),
                ],
            ),
            focused_element=input_field,
        )

    def _get_status_bar_text(self):
        if self._is_thinking:
            return [("class:thinking", f" {self._assistant_name} is thinking... ")]
        return [("class:status", " Ready ")]

    def _create_output_keybindings(self, input_field: TextArea):
        kb = KeyBindings()

        @kb.add("c-c")
        def _(event):
            # Copy selection to clipboard
            data = event.current_buffer.copy_selection()
            event.app.clipboard.set_data(data)

        def redirect_focus(event):
            get_app().layout.focus(input_field)
            input_field.buffer.insert_text(event.data)

        for char in string.printable:
            # Skip control characters (Tab, Newline, etc.)
            #  to preserve navigation/standard behavior
            if char in "\t\n\r\x0b\x0c":
                continue
            kb.add(char)(redirect_focus)

        return kb

    def _setup_app_keybindings(self, app_keybindings: KeyBindings, llm_task: AnyTask):
        @app_keybindings.add("c-c")
        def _(event):
            # If text is selected, copy it instead of exiting
            buffer = event.app.current_buffer
            if buffer.selection_state:
                data = buffer.copy_selection()
                event.app.clipboard.set_data(data)
                buffer.exit_selection()
                return
            event.app.exit()

        @app_keybindings.add("escape")
        def _(event):
            if self._running_llm_task and not self._running_llm_task.done():
                self._running_llm_task.cancel()
                self.append_to_output("\n<Esc> Canceled")


        @app_keybindings.add("enter")
        def _(event):
            buff = event.current_buffer
            text = buff.text

            # Handle confirmation if waiting
            if self._waiting_for_confirmation and self._confirmation_future:
                # Echo the user input
                self.append_to_output(text + "\n")
                if not self._confirmation_future.done():
                    self._confirmation_future.set_result(text)
                buff.reset()
                return

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
                        return

            # If input is empty, do nothing
            if not text.strip():
                return

            if text.strip().lower() in EXIT_COMMANDS:
                event.app.exit()
                return

            if text.strip().lower().startswith("/attach "):
                path = text.strip()[8:].strip()
                self._handle_attach_command(path)
                buff.reset()
                return

            # If we are thinking, ignore input
            if self._is_thinking:
                return

            self._submit_user_message(llm_task, text)
            buff.reset()

        @app_keybindings.add("c-j")  # Ctrl+J
        @app_keybindings.add("c-space")  # Ctrl+Space (Fallback)
        def _(event):
            event.current_buffer.insert_text("\n")

    def _handle_attach_command(self, path: str):
        # Validate path
        import os

        expanded_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(expanded_path):
            self.append_to_output(f"\n❌ File not found: {path}\n")
            return

        if expanded_path not in self._pending_attachments:
            self._pending_attachments.append(expanded_path)
            self.append_to_output(f"\n📎 Attached: {path}\n")
        else:
            self.append_to_output(f"\n📎 Already attached: {path}\n")

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        # Helper to safely append to read-only buffer
        current_text = self._output_field.text

        # Construct the new content
        content = sep.join([str(value) for value in values]) + end

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

        # Update content directly
        # We use bypass_readonly=True by constructing a Document
        self._output_field.buffer.set_document(
            Document(new_text, cursor_position=len(new_text)), bypass_readonly=True
        )
        get_app().invalidate()

    def _submit_user_message(self, llm_task: AnyTask, user_message: str):
        timestamp = datetime.now().strftime("%H:%M")

        # 1. Render User Message
        user_header = f"💬 {timestamp} >>\n"
        self.append_to_output(f"\n{user_header}{user_message.strip()}\n")

        # 2. Trigger AI Response
        attachments = list(self._pending_attachments)
        self._pending_attachments.clear()

        self._running_llm_task = asyncio.create_task(
            self._stream_ai_response(llm_task, user_message, attachments)
        )

    async def _stream_ai_response(
        self, llm_task: AnyTask, user_message: str, attachments: list[str] = []
    ):
        from zrb.llm.agent.agent import tool_confirmation_var

        self._is_thinking = True
        get_app().invalidate()  # Update status bar

        try:
            timestamp = datetime.now().strftime("%H:%M")
            ai_header = f"🤖 {timestamp} >>\n"
            # Header first
            self.append_to_output(f"\n{ai_header}")

            session_input = {
                "message": user_message,
                "session": self._conversation_session_name,
                "yolo": self._yolo,
                "attachments": attachments,
            }

            shared_ctx = SharedContext(
                input=session_input,
                print_fn=self.append_to_output,
                is_web_mode=True,
            )
            session = Session(shared_ctx)

            # Run the task with stdout/stderr redirected to UI
            stdout_capture = StdoutToUI(self.append_to_output)

            # Set context var for tool confirmation
            token = tool_confirmation_var.set(self._confirm_tool_execution)
            try:
                with contextlib.redirect_stdout(
                    stdout_capture
                ), contextlib.redirect_stderr(stdout_capture):
                    result_data = await llm_task.async_run(session)
            finally:
                tool_confirmation_var.reset(token)

            # Check for final text output
            if result_data is not None:
                if isinstance(result_data, str):
                    # Ensure new line after stream before final output
                    self.append_to_output("\n")
                    self.append_to_output(result_data)

        except asyncio.CancelledError:
            self.append_to_output("\n[Cancelled]\n")
        except Exception as e:
            with open("zrb_debug.log", "a") as f:
                f.write(f"[{datetime.now()}] Error: {e}\n")
            self.append_to_output(f"\n[Error: {e}]\n")
        finally:
            self._is_thinking = False
            self._running_llm_task = None
            get_app().invalidate()
