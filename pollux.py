#!/usr/bin/env python3
"""
Pollux CLI - A Gemini-inspired terminal chat interface.
Mock AI implementation with high-fidelity UI/UX details.
"""

import asyncio
import random
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

from zrb import AnyContext, make_task

# --- Constants & Mock Data ---

LOREM_IPSUM = [
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
    "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
    "Curabitur pretium tincidunt lacus. Nulla gravida orci a odio.",
    "Nullam varius, turpis et commodo pharetra, est eros bibendum elit, nec luctus magna felis sollicitudin mauris.",
    "Integer in mauris eu nibh euismod gravida.",
    "Duis ac tellus et risus vulputate vehicula.",
    "Donec lobortis risus a elit. Etiam tempor.",
    "Ut ullamcorper, ligula eu tempor congue, eros est euismod turpis, id tincidunt sapien risus a quam.",
    "Maecenas fermentum consequat mi. Donec fermentum.",
    "Pellentesque malesuada nulla a mi. Duis sapien sem, aliquet nec, commodo eget, consequat quis, neque.",
    "Aliquam faucibus, elit ut dictum aliquet, felis nisl adipiscing sapien, sed malesuada diam lacus eget erat.",
    "Cras mollis scelerisque nunc. Nullam arcu.",
]

GEMINI_GREETING = """
  /\\
 /  \\   Pollux AI
/    \\  v1.0.0
\\    /
 \\  /   Welcome! I am Pollux.
  \\/    How can I help you today?
"""

# --- Custom Lexer for Syntax Highlighting ---


class ChatLexer(Lexer):
    def lex_document(self, document):
        # A simple lexer to colorize User and AI names
        def get_line(lineno):
            line = document.lines[lineno]
            tokens = []

            # Simple parsing logic
            if line.startswith("User"):
                # "User" mock-up
                # Assume format: "User   <timestamp>"
                # We split by parts for basic coloring
                parts = line.split(" ", 1)
                tokens.append(("class:username", parts[0]))
                if len(parts) > 1:
                    tokens.append(("", " " + parts[1]))

            elif line.startswith("Pollux"):
                parts = line.split(" ", 1)
                tokens.append(("class:ai_name", parts[0]))
                if len(parts) > 1:
                    tokens.append(("", " " + parts[1]))

            elif line.startswith("Thinking..."):
                tokens.append(("class:thinking", line))

            else:
                # content
                tokens.append(("class:text", line))

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
            lexer=ChatLexer(),
            focus_on_click=True,
        )

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
        sep: str = "",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        # Helper to safely append to read-only buffer
        current_text = self.output_field.text
        text = sep.join([f"{value}" for value in values])

        new_text = current_text + text + end

        # Update content directly
        # We use bypass_readonly=True by constructing a Document
        self.output_field.buffer.set_document(
            Document(new_text, cursor_position=len(new_text)), bypass_readonly=True
        )

    def submit_message(self, text):
        timestamp = datetime.now().strftime("%H:%M")

        # 1. Render User Message
        user_header = f"User   {timestamp}\n"
        separator = "-" * 40 + "\n"
        self.append_to_output(f"\n{user_header}{separator}{text.strip()}\n")

        # 2. Trigger AI Response
        asyncio.create_task(self.stream_ai_response())

    async def stream_ai_response(self):
        self.is_thinking = True
        get_app().invalidate()  # Update status bar

        # Simulate network delay / "Thinking"
        await asyncio.sleep(random.uniform(0.5, 1.5))

        timestamp = datetime.now().strftime("%H:%M")
        ai_header = f"Pollux   {timestamp}\n"
        separator = "-" * 40 + "\n"

        # Header first
        self.append_to_output(f"\n{ai_header}{separator}")

        ai_task = self.create_ai_task()
        await ai_task.async_run()

        self.append_to_output("\n")
        self.is_thinking = False
        get_app().invalidate()

    def create_ai_task(self):

        @make_task(
            name="coba",
            print_fn=self.append_to_output,
        )
        async def ai_task(ctx: AnyContext):
            num_paragraphs = random.randint(1, 3)
            paragraphs = random.sample(
                LOREM_IPSUM, min(len(LOREM_IPSUM), num_paragraphs * 3)
            )
            # Stream word by word
            for i, para in enumerate(paragraphs):
                words = para.split(" ")
                for word in words:
                    chunk = word + " "
                    ctx.print(chunk, end="", plain=True)
                    # self.append_to_output(chunk)
                    # Random typing speed
                    await asyncio.sleep(random.uniform(0.02, 0.1))

                # Newline between paragraphs
                if i < len(paragraphs) - 1:
                    ctx.print("\n\n", end="", plain=True)
                    # self.append_to_output("\n\n")
                    await asyncio.sleep(0.3)

        return ai_task

    def run(self):
        # We need to run async to support the streaming task
        asyncio.run(self.application.run_async())


if __name__ == "__main__":
    app = PolluxApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
