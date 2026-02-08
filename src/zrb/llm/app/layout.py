from typing import Callable

from prompt_toolkit.filters import (
    Condition,
    emacs_insert_mode,
    has_selection,
    vi_insert_mode,
)
from prompt_toolkit.formatted_text import HTML, AnyFormattedText
from prompt_toolkit.history import History
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    HSplit,
    Layout,
    Window,
    WindowAlign,
)
from prompt_toolkit.layout.containers import Float, FloatContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.widgets import Frame, TextArea

from zrb.llm.app.completion import InputCompleter
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager


def create_input_field(
    history_manager: AnyHistoryManager,
    attach_commands: list[str],
    exit_commands: list[str],
    info_commands: list[str],
    save_commands: list[str],
    load_commands: list[str],
    redirect_output_commands: list[str],
    summarize_commands: list[str],
    set_model_commands: list[str],
    exec_commands: list[str],
    custom_commands: list[AnyCustomCommand],
    history: History | None = None,
) -> TextArea:
    class DynamicHeightTextArea(TextArea):
        """TextArea with dynamic height based on content."""

        def __init__(self, *args, **kwargs):
            # Remove fixed height, will be calculated dynamically
            if "height" in kwargs:
                del kwargs["height"]
            super().__init__(*args, **kwargs)

        def preferred_height(
            self,
            width: int,
            max_available_height: int,
            wrap_lines: bool,
            get_line_prefix,
        ) -> int:
            """Calculate preferred height based on content."""
            # Get current text
            text = self.text
            # Count lines (including wrapped lines)
            line_count = text.count("\n") + 1

            # Calculate how many lines would be needed with wrapping
            if wrap_lines and width > 0:
                wrapped_lines = 0
                for line in text.split("\n"):
                    # Estimate wrapped lines (ceil division)
                    wrapped_lines += (
                        (len(line) + width - 1) // width if len(line) > 0 else 1
                    )
                line_count = max(line_count, wrapped_lines)

            # Start with 1 line (just the prompt line)
            # The prompt line is included in the TextArea's rendering
            # So total height should be just the content lines
            return min(max(line_count, 1), 10)

    text_area = DynamicHeightTextArea(
        prompt=HTML('<style color="ansibrightblue"><b>&gt;&gt;&gt; </b></style>'),
        multiline=True,
        wrap_lines=True,
        history=history,
        completer=InputCompleter(
            history_manager=history_manager,
            attach_commands=attach_commands,
            exit_commands=exit_commands,
            info_commands=info_commands,
            save_commands=save_commands,
            load_commands=load_commands,
            redirect_output_commands=redirect_output_commands,
            summarize_commands=summarize_commands,
            set_model_commands=set_model_commands,
            exec_commands=exec_commands,
            custom_commands=custom_commands,
        ),
        complete_while_typing=True,
        focus_on_click=True,
        style="class:input_field",
        dont_extend_height=True,  # Don't let it be compressed
    )

    # Add custom keybindings for history navigation
    # TextArea doesn't accept key_bindings in __init__, we must add them to its control
    kb = text_area.control.key_bindings
    if kb is None:
        kb = KeyBindings()
        text_area.control.key_bindings = kb

    @Condition
    def is_first_line() -> bool:
        return text_area.document.cursor_position_row == 0

    @Condition
    def is_last_line() -> bool:
        return (
            text_area.document.cursor_position_row == text_area.document.line_count - 1
        )

    # Bind Up to history only if at first line
    @kb.add("up", filter=is_first_line & ~has_selection)
    def _(event):
        event.current_buffer.history_backward()

    # Bind Down to history only if at last line
    @kb.add("down", filter=is_last_line & ~has_selection)
    def _(event):
        event.current_buffer.history_forward()

    # Ensure Paste works locally in the input field
    @kb.add("c-v")
    def _(event):
        event.current_buffer.paste_clipboard_data(event.app.clipboard.get_data())

    return text_area


def create_output_field(greeting: str, lexer: Lexer) -> TextArea:
    # Create TextArea with cursor at the end to ensure bottom is visible
    text_area = TextArea(
        text=greeting.rstrip() + "\n\n",
        read_only=True,
        scrollbar=False,  # No scrollbar on TextArea itself
        wrap_lines=True,
        lexer=lexer,
        focus_on_click=True,
        focusable=True,
        style="class:output_field",
        dont_extend_height=False,  # Can expand/contract as needed
    )
    # Set cursor to the end - TextArea will keep cursor visible when focusable
    text_area.buffer.cursor_position = len(text_area.text)
    return text_area


def create_layout(
    title: str,
    jargon: str,
    input_field: TextArea,
    output_field: TextArea,
    info_bar_text: Callable[[], AnyFormattedText],
    status_bar_text: Callable[[], AnyFormattedText],
) -> Layout:
    title_bar_text = HTML(
        f" <style bg='ansipurple' color='white'><b> {title} </b></style> "
        f"<style color='#888888'>| {jargon}</style>"
    )

    return Layout(
        FloatContainer(
            content=HSplit(
                [
                    # Title Bar (fixed height)
                    Window(
                        height=2,
                        content=FormattedTextControl(title_bar_text),
                        style="class:title-bar",
                        align=WindowAlign.CENTER,
                    ),
                    # Info Bar (fixed height)
                    Window(
                        height=3,
                        content=FormattedTextControl(info_bar_text),
                        style="class:info-bar",
                    ),
                    # Chat History - NO FRAME, NO ScrollablePane
                    # Just the TextArea itself - it handles its own scrolling
                    output_field,
                    # Input Area with frame (centered title) - with padding
                    Window(height=1),  # Top margin
                    Frame(
                        input_field,
                        title="(ENTER to send, CTRL+j for newline, ESC to cancel)",
                        style="class:input-frame",
                    ),
                    Window(height=1),  # Bottom padding
                    # Status Bar (fixed height)
                    Window(
                        height=1,
                        content=FormattedTextControl(status_bar_text),
                        style="class:bottom-toolbar",
                    ),
                ],
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
