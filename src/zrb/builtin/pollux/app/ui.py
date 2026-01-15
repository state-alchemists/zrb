import asyncio
import re
import string
from datetime import datetime
from typing import TextIO

from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML, AnyFormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window, WindowAlign
from prompt_toolkit.layout.containers import Float, FloatContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.util.cli.markdown import render_markdown

EXIT_COMMANDS = ["/q", "/bye", "/quit", "/exit"]


class UI:
    def __init__(
        self,
        greeting: str,
        assistant_name: str,
        jargon: str,
        output_lexer: Lexer,
        llm_task: AnyTask,
    ):
        self._is_thinking = False
        self._running_llm_task: asyncio.Task | None = None
        self._llm_task = llm_task
        self._assistant_name = assistant_name
        self._jargon = jargon
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

    @property
    def application(self) -> Application:
        return self._application

    def _create_style(self) -> Style:
        return Style.from_dict(
            {
                "frame.label": "bg:#ffffff #000000",
                "username": "ansibrightblue bold",
                "ai_name": "ansipurple bold",
                "thinking": "ansigreen italic",
                "faint": "#888888",
                "text": "#eeeeee",
                "status": "reverse",
                "bottom-toolbar": "bg:#333333 #aaaaaa",
            }
        )

    def _create_output_field(self, greeting: str, lexer: Lexer) -> TextArea:
        return TextArea(
            text=greeting.rstrip() + "\n\n",
            read_only=True,
            scrollbar=True,
            wrap_lines=True,
            lexer=lexer,
            focus_on_click=True,
            focusable=True,
        )

    def _create_input_field(self) -> TextArea:
        return TextArea(
            height=4,
            prompt=HTML('<style color="ansibrightblue"><b>&gt;&gt;&gt; </b></style>'),
            multiline=True,
            wrap_lines=True,
            completer=WordCompleter(EXIT_COMMANDS, ignore_case=True, WORD=True),
            complete_while_typing=True,
        )

    def _create_application(
        self, layout: Layout, keybindings: KeyBindings, style: Style
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
                            title="Input (Enter to send, Ctrl+enter or Ctrl+J for newline)",
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
            event.app.exit()

        @app_keybindings.add("escape")
        def _(event):
            if self._running_llm_task and not self._running_llm_task.done():
                self._running_llm_task.cancel()

        @app_keybindings.add("enter")
        def _(event):
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
                        return

            # If input is empty, do nothing
            if not text.strip():
                return

            if text.strip().lower() in EXIT_COMMANDS:
                event.app.exit()
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

    def _append_to_output(
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

    def _submit_user_message(self, llm_task: AnyTask, user_message: str):
        timestamp = datetime.now().strftime("%H:%M")

        # 1. Render User Message
        user_header = f"💬 {timestamp} >>\n"
        self._append_to_output(f"\n{user_header}{user_message.strip()}\n")

        # 2. Trigger AI Response
        self._running_llm_task = asyncio.create_task(
            self._stream_ai_response(llm_task, user_message)
        )

    async def _stream_ai_response(self, llm_task: AnyTask, user_message: str):
        self._is_thinking = True
        get_app().invalidate()  # Update status bar

        try:
            timestamp = datetime.now().strftime("%H:%M")
            ai_header = f"🤖 {timestamp} >>\n"
            # Header first
            self._append_to_output(f"\n{ai_header}")
            session = Session(
                SharedContext(
                    input={"message": user_message},
                    print_fn=self._append_to_output,
                    is_web_mode=True,
                )
            )
            result = await llm_task.async_run(session)
            if result is not None:
                self._append_to_output("\n")
                if hasattr(result, "output"):
                    output = getattr(result, "output")
                    self._append_to_output(render_markdown(output))

            self._append_to_output("\n")
        except asyncio.CancelledError:
            self._append_to_output("\n[Cancelled]\n")
        except Exception as e:
            self._append_to_output(f"\n[Error: {e}]\n")
        finally:
            self._is_thinking = False
            self._running_llm_task = None
            get_app().invalidate()
