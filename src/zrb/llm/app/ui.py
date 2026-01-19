import asyncio
import contextlib
import os
import re
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, TextIO

from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style

from zrb.context.shared_context import SharedContext
from zrb.llm.app.confirmation.handler import (
    ConfirmationHandler,
    ConfirmationMiddleware,
    last_confirmation,
)
from zrb.llm.app.keybinding import create_output_keybindings
from zrb.llm.app.layout import create_input_field, create_layout, create_output_field
from zrb.llm.app.redirection import StreamToUI
from zrb.llm.app.style import create_style
from zrb.llm.task.llm_task import LLMTask
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.util.cli.markdown import render_markdown
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from pydantic_ai import UserContent
    from pydantic_ai.models import Model
    from rich.theme import Theme


class UI:
    def __init__(
        self,
        greeting: str,
        assistant_name: str,
        jargon: str,
        output_lexer: Lexer,
        llm_task: LLMTask,
        initial_message: Any = "",
        initial_attachments: "list[UserContent]" = [],
        conversation_session_name: str = "",
        yolo: bool = False,
        triggers: list[Callable[[], Any]] = [],
        confirmation_middlewares: list[ConfirmationMiddleware] = [],
        markdown_theme: "Theme | None" = None,
        summarize_commands: list[str] = [],
        attach_commands: list[str] = [],
        exit_commands: list[str] = [],
        info_commands: list[str] = [],
        save_commands: list[str] = [],
        load_commands: list[str] = [],
        redirect_output_commands: list[str] = [],
        model: "Model | str | None" = None,
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
        self._model = model
        self._triggers = triggers
        self._markdown_theme = markdown_theme
        self._summarize_commands = summarize_commands
        self._attach_commands = attach_commands
        self._exit_commands = exit_commands
        self._info_commands = info_commands
        self._save_commands = save_commands
        self._load_commands = load_commands
        self._redirect_output_commands = redirect_output_commands
        self._trigger_tasks: list[asyncio.Task] = []
        # Attachments
        self._pending_attachments: "list[UserContent]" = list(initial_attachments)
        # Confirmation Handler
        self._confirmation_handler = ConfirmationHandler(
            middlewares=confirmation_middlewares + [last_confirmation]
        )
        # Confirmation state (Used by ask_user and keybindings)
        self._waiting_for_confirmation = False
        self._confirmation_future: asyncio.Future[str] | None = None
        # UI Styles
        self._style = create_style()
        # Input Area
        self._input_field = create_input_field(
            attach_commands=self._attach_commands,
            exit_commands=self._exit_commands,
            info_commands=self._info_commands,
            save_commands=self._save_commands,
            load_commands=self._load_commands,
            redirect_output_commands=self._redirect_output_commands,
            summarize_commands=self._summarize_commands,
        )
        # Output Area (Read-only chat history)
        self._output_field = create_output_field(greeting, output_lexer)
        self._output_field.control.key_bindings = create_output_keybindings(
            self._input_field
        )
        self._layout = create_layout(
            title=self._assistant_name,
            jargon=self._jargon,
            input_field=self._input_field,
            output_field=self._output_field,
            info_bar_text=self._get_info_bar_text,
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
        import logging

        # Start triggers
        for trigger_fn in self._triggers:
            trigger_task = self._application.create_background_task(
                self._trigger_loop(trigger_fn)
            )
            self._trigger_tasks.append(trigger_task)

        # Setup logging redirection to UI
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]

        ui_stream = StreamToUI(self.append_to_output)
        ui_handler = logging.StreamHandler(ui_stream)
        formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        ui_handler.setFormatter(formatter)

        root_logger.handlers = [ui_handler]

        try:
            with patch_stdout():
                return await self._application.run_async()
        finally:
            # Restore handlers
            root_logger.handlers = original_handlers

            # Stop triggers
            for trigger_task in self._trigger_tasks:
                trigger_task.cancel()
            self._trigger_tasks.clear()

    async def _trigger_loop(self, trigger_fn: Callable[[], Any]):
        """Handle external triggers and submit user message when trigger activated"""
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
        """Handle initial message (the message sent when creating the UI)"""
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

    def _get_info_bar_text(self) -> AnyFormattedText:
        from prompt_toolkit.formatted_text import HTML

        model_name = "Unknown"
        if self._model:
            if isinstance(self._model, str):
                model_name = self._model
            elif hasattr(self._model, "model_name"):
                model_name = getattr(self._model, "model_name")
            else:
                model_name = str(self._model)
        yolo_text = (
            "<style color='ansired'><b>ON</b></style>"
            if self._yolo
            else "<style color='ansigreen'>OFF</style>"
        )
        return HTML(
            f" 🤖 <b>Model:</b> {model_name} "
            f"| 🗣️ <b>Session:</b> {self._conversation_session_name} "
            f"| 🤠 <b>YOLO:</b> {yolo_text} "
        )

    def _get_status_bar_text(self) -> AnyFormattedText:
        if self._is_thinking:
            return [("class:thinking", f" {self._assistant_name} is thinking... ")]
        return [("class:status", " Ready ")]

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
            # Handle confirmation and multiline
            if self._handle_confirmation(event):
                return
            if self._handle_multiline(event):
                return

            # Handle empty inputs
            buff = event.current_buffer
            text = buff.text
            if not text.strip():
                return

            # Handle other commands
            if self._handle_exit_command(event):
                return
            if self._handle_attach_command(event):
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
        if self._waiting_for_confirmation and self._confirmation_future:
            # Echo the user input
            self.append_to_output(text + "\n")
            if not self._confirmation_future.done():
                self._confirmation_future.set_result(text)
            buff.reset()
            return True
        return False

    def _handle_exit_command(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        if text.strip().lower() in self._exit_commands:
            event.app.exit()
            return True
        return False

    def _handle_attach_command(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        for attach_command in self._attach_commands:
            if text.strip().lower().startswith(f"{attach_command} "):
                path = text.strip()[8:].strip()
                self._submit_attachment(path)
                buff.reset()
                return True
        return False

    def _submit_attachment(self, path: str):
        # Validate path
        self.append_to_output(f"\n  🔢 Attach {path}...\n")
        expanded_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(expanded_path):
            self.append_to_output(f"\n  ❌ File not found: {path}\n")
            return
        if expanded_path not in self._pending_attachments:
            self._pending_attachments.append(expanded_path)
            self.append_to_output(f"\n  📎 Attached: {path}\n")
        else:
            self.append_to_output(f"\n  📎 Already attached: {path}\n")

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
        self.append_to_output(f"\n💬 {timestamp} >>\n{user_message.strip()}\n")
        # 2. Trigger AI Response
        attachments = list(self._pending_attachments)
        self._pending_attachments.clear()
        self._running_llm_task = asyncio.create_task(
            self._stream_ai_response(llm_task, user_message, attachments)
        )

    async def _stream_ai_response(
        self,
        llm_task: AnyTask,
        user_message: str,
        attachments: "list[UserContent]" = [],
    ):
        from zrb.llm.agent.agent import tool_confirmation_var

        self._is_thinking = True
        get_app().invalidate()  # Update status bar
        try:
            timestamp = datetime.now().strftime("%H:%M")
            # Header first
            self.append_to_output(f"\n🤖 {timestamp} >>\n")
            session = self._create_sesion_for_llm_task(user_message, attachments)

            # Run the task with stdout/stderr redirected to UI
            self.append_to_output("\n  🔢 Streaming response...\n")
            stdout_capture = StreamToUI(self.append_to_output)

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
                    width = self._get_output_field_width()
                    self.append_to_output("\n")
                    self.append_to_output(
                        render_markdown(
                            result_data, width=width, theme=self._markdown_theme
                        )
                    )

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

    def _create_sesion_for_llm_task(
        self, user_message: str, attachments: "list[UserContent]"
    ) -> AnySession:
        """Create session to run LLMTask"""
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
        return Session(shared_ctx)

    def _get_output_field_width(self) -> int | None:
        try:
            width = get_app().output.get_size().columns - 4
            if width < 10:
                width = None
        except Exception:
            width = None
        return width
