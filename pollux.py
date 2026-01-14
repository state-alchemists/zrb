#!/usr/bin/env python3
"""
Pollux CLI - A Gemini-inspired terminal chat interface.
Mock AI implementation with high-fidelity UI/UX details.
"""

import os

# Disable LLMTask escape detection to prevent terminal interference
os.environ["ZRB_DISABLE_LLM_ESCAPE_DETECTION"] = "1"

import asyncio
import random
import re
import string
from datetime import datetime
from typing import TextIO

from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window, WindowAlign
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from zrb import LLMTask, Session, SharedContext, StrInput, Task
from zrb.util.cli.markdown import render_markdown

# --- Constants & Mock Data ---

GEMINI_GREETING = """
  /\\
 /  \\   Pollux AI
/    \\  v1.0.0
\\    /
 \\  /   Welcome! I am Pollux.
  \\/    How can I help you today?
"""

# --- Custom Lexer for Syntax Highlighting ---


class CLIStyleLexer(Lexer):
    def lex_document(self, document):
        def get_line(lineno):
            line = document.lines[lineno]
            tokens = []

            # Regex to find ANSI escape sequences
            ansi_escape = re.compile(r"\x1B\[[0-9;]*[mK]")

            last_end = 0
            current_style = ""

            for match in ansi_escape.finditer(line):
                start, end = match.span()

                # Add text before the escape sequence with current style
                if start > last_end:
                    tokens.append((current_style, line[last_end:start]))

                # Parse the escape sequence to update style
                sequence = match.group()
                if sequence == "\x1b[0m":
                    current_style = ""  # Reset
                else:
                    # Simple mapping for common colors/styles used in zrb
                    # This is a basic implementation and might need expansion
                    if "1" in sequence:
                        current_style += "bold "
                    if "2" in sequence:
                        current_style += "class:faint "
                    if "3" in sequence:
                        current_style += "italic "  # Italic is 3 in zrb style
                    if "30" in sequence:
                        current_style += "#000000 "
                    if "31" in sequence:
                        current_style += "#ff0000 "
                    if "32" in sequence:
                        current_style += "#00ff00 "
                    if "33" in sequence:
                        current_style += "#ffff00 "
                    if "34" in sequence:
                        current_style += "#0000ff "
                    if "35" in sequence:
                        current_style += "#ff00ff "
                    if "36" in sequence:
                        current_style += "#00ffff "
                    if "37" in sequence:
                        current_style += "#ffffff "
                    # Bright colors
                    if "90" in sequence:
                        current_style += "#555555 "
                    if "91" in sequence:
                        current_style += "#ff5555 "
                    if "92" in sequence:
                        current_style += "#55ff55 "
                    if "93" in sequence:
                        current_style += "#ffff55 "
                    if "94" in sequence:
                        current_style += "#5555ff "
                    if "95" in sequence:
                        current_style += "#ff55ff "
                    if "96" in sequence:
                        current_style += "#55ffff "
                    if "97" in sequence:
                        current_style += "#ffffff "

                last_end = end

            # Add remaining text
            if last_end < len(line):
                tokens.append((current_style, line[last_end:]))

            return tokens

        return get_line


# --- Main Application Logic ---


class PolluxApp:
    def __init__(self):
        self.is_thinking = False

        # UI Styles
        self.style = Style.from_dict(
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

        # Output Area (Read-only chat history)
        self.output_field = TextArea(
            text=GEMINI_GREETING.rstrip() + "\n\n",
            read_only=True,
            scrollbar=True,
            wrap_lines=True,
            lexer=CLIStyleLexer(),
            focus_on_click=True,
            focusable=True,
        )
        self.output_field.control.key_bindings = self._create_output_keybindings()

        # Input Area
        self.input_field = TextArea(
            height=4,
            prompt=HTML('<style color="ansibrightblue"><b>&gt;&gt;&gt; </b></style>'),
            multiline=True,
            wrap_lines=True,
        )

        # Key Bindings
        self.kb = KeyBindings()
        self._setup_keybindings()

        # Layout
        self.layout = Layout(
            HSplit(
                [
                    # Title Bar
                    Window(
                        height=1,
                        content=FormattedTextControl(
                            HTML(
                                " <style bg='ansipurple' color='white'><b> Pollux </b></style> "
                                "<style color='#888888'>| AI Assistant Prototype</style>"
                            )
                        ),
                        style="class:title-bar",
                        align=WindowAlign.CENTER,
                    ),
                    # Chat History
                    Frame(self.output_field, title="Conversation", style="class:frame"),
                    # Input Area
                    Frame(
                        self.input_field,
                        title="Input (Enter to send, \\+Enter or Ctrl+Space for newline)",
                        style="class:input-frame",
                    ),
                    # Status Bar
                    Window(
                        height=1,
                        content=FormattedTextControl(self.get_status_bar_text),
                        style="class:bottom-toolbar",
                    ),
                ]
            ),
            focused_element=self.input_field,
        )

        self.application = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=self.style,
            full_screen=True,
            mouse_support=True,
        )

    def get_status_bar_text(self):
        if self.is_thinking:
            return [("class:thinking", " Pollux is thinking... ")]
        return [("class:status", " Ready ")]

    def _create_output_keybindings(self):
        kb = KeyBindings()

        def redirect_focus(event):
            get_app().layout.focus(self.input_field)
            self.input_field.buffer.insert_text(event.data)

        for char in string.printable:
            # Skip control characters (Tab, Newline, etc.) to preserve navigation/standard behavior
            if char in "\t\n\r\x0b\x0c":
                continue
            kb.add(char)(redirect_focus)

        return kb

    def _setup_keybindings(self):
        @self.kb.add("c-c")
        def _(event):
            event.app.exit()

        @self.kb.add("enter")
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

            # If we are thinking, ignore input
            if self.is_thinking:
                return

            self.submit_message(text)
            buff.reset()

        @self.kb.add("escape", "enter")  # Alt+Enter (ESC + Enter)
        @self.kb.add("c-space")  # Ctrl+Space (Fallback)
        def _(event):
            event.current_buffer.insert_text("\n")

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        # Helper to safely append to read-only buffer
        current_text = self.output_field.text

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
        self.output_field.buffer.set_document(
            Document(new_text, cursor_position=len(new_text)), bypass_readonly=True
        )

    def submit_message(self, user_message):
        timestamp = datetime.now().strftime("%H:%M")

        # 1. Render User Message
        user_header = f"User   {timestamp}\n"
        separator = "-" * 40 + "\n"
        self.append_to_output(f"\n{user_header}{separator}{user_message.strip()}\n")

        # 2. Trigger AI Response
        asyncio.create_task(self.stream_ai_response(user_message))

    async def stream_ai_response(self, user_message):
        self.is_thinking = True
        get_app().invalidate()  # Update status bar

        # Simulate network delay / "Thinking"
        await asyncio.sleep(random.uniform(0.5, 1.5))

        timestamp = datetime.now().strftime("%H:%M")
        ai_header = f"Pollux   {timestamp}\n"
        separator = "-" * 40 + "\n"

        # Header first
        self.append_to_output(f"\n{ai_header}{separator}")

        session = Session(
            SharedContext(
                input={"message": user_message},
                print_fn=self.append_to_output,
                is_web_mode=True,
            )
        )
        llm_ask = self.create_task_llm()
        result = await llm_ask.async_run(session)
        if result is not None:
            self.append_to_output("\n")
            self.append_to_output(render_markdown(result))

        self.append_to_output("\n")
        self.is_thinking = False
        get_app().invalidate()

    def create_task_llm(self):
        return LLMTask(
            name="llm-anu", input=[StrInput("message")], message="{ctx.input.message}"
        )

    def create_task(self):
        return Task(
            name="coba",
            input=[StrInput("message")],
            action=lambda ctx: ctx.print(ctx.input.message),
        )

    def run(self):
        # We need to run async to support the streaming task
        asyncio.run(self.application.run_async())


if __name__ == "__main__":
    app = PolluxApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
