from typing import Callable, cast

from prompt_toolkit.filters import (
    Condition,
    has_completions,
    has_selection,
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
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    Float,
    FloatContainer,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.mouse_events import MouseEventType
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
    rewind_commands: list[str] = [],
    redirect_output_commands: list[str] = [],
    summarize_commands: list[str] = [],
    set_model_commands: list[str] = [],
    exec_commands: list[str] = [],
    btw_commands: list[str] = [],
    plan_commands: list[str] = [],
    copy_commands: list[str] = [],
    voice_commands: list[str] = [],
    custom_commands: list[AnyCustomCommand] = [],
    history: History | None = None,
    custom_model_names: list[str] = [],
    show_ollama_models: bool = True,
    show_pydantic_ai_models: bool = True,
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
            rewind_commands=rewind_commands,
            redirect_output_commands=redirect_output_commands,
            summarize_commands=summarize_commands,
            set_model_commands=set_model_commands,
            exec_commands=exec_commands,
            btw_commands=btw_commands,
            plan_commands=plan_commands,
            copy_commands=copy_commands,
            voice_commands=voice_commands,
            custom_commands=custom_commands,
            custom_model_names=custom_model_names,
            show_ollama_models=show_ollama_models,
            show_pydantic_ai_models=show_pydantic_ai_models,
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
    kb = cast(KeyBindings, kb)

    @Condition
    def is_first_line() -> bool:
        return text_area.document.cursor_position_row == 0

    @Condition
    def is_last_line() -> bool:
        return (
            text_area.document.cursor_position_row == text_area.document.line_count - 1
        )

    # Bind Up to history only if at first line and no completion menu is shown
    @kb.add("up", filter=is_first_line & ~has_selection & ~has_completions)
    def _(event):
        event.current_buffer.history_backward()

    # Bind Down to history only if at last line and no completion menu is shown
    @kb.add("down", filter=is_last_line & ~has_selection & ~has_completions)
    def _(event):
        event.current_buffer.history_forward()

    # Focus traversal is handled by Tab at the app level; Tab still drives
    # completion-menu navigation when a menu is open (the app-level binding
    # is gated by ~has_completions). Shift+Tab is deliberately unbound here
    # so the app-level binding can cycle modes. See ADR-0075.

    return text_area


def create_output_field(
    greeting: str, lexer: Lexer, key_bindings: KeyBindings | None = None
) -> TextArea:
    def get_line_prefix(line_number: int, wrap_number: int) -> AnyFormattedText:
        return " "

    # Create TextArea with cursor at the end to ensure bottom is visible
    text_area = TextArea(
        text=greeting.rstrip() + "\n\n",
        read_only=True,
        scrollbar=False,
        wrap_lines=True,
        lexer=lexer,
        focus_on_click=True,
        focusable=True,
        get_line_prefix=get_line_prefix,
        style="class:output_field",
        dont_extend_height=False,  # Can expand/contract as needed
    )
    if key_bindings is not None:
        text_area.control.key_bindings = key_bindings

    _bind_scroll_to_cursor(text_area)

    # Set cursor to the end - TextArea will keep cursor visible when focusable
    text_area.buffer.cursor_position = len(text_area.text)
    return text_area


def _bind_scroll_to_cursor(text_area: TextArea, lines: int = 3) -> None:
    """Make the mouse wheel move the output cursor instead of the viewport.

    The output window pins itself to the cursor, so prompt_toolkit's default
    wheel handling (nudging vertical_scroll) gets snapped straight back to the
    bottom by the next streamed chunk. Moving the cursor itself scrolls the
    window for real and — because the cursor leaves the last line — pauses the
    auto-follow in append_to_output. Intercepting on the control handles scroll
    regardless of which pane is focused, so no Ctrl+K is needed first.
    """
    control = text_area.control
    inner_handler = control.mouse_handler

    def mouse_handler(mouse_event):
        buf = text_area.buffer
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            buf.cursor_position += buf.document.get_cursor_up_position(count=lines)
            return None
        if mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            buf.cursor_position += buf.document.get_cursor_down_position(count=lines)
            return None
        return inner_handler(mouse_event)

    control.mouse_handler = mouse_handler


def create_layout(
    title: str,
    jargon: str,
    input_field: TextArea,
    output_field: TextArea,
    info_bar_text: Callable[[], AnyFormattedText],
    status_bar_text: Callable[[], AnyFormattedText],
    extra_floats: list[Float] | None = None,
    agent_activity_text: Callable[[], AnyFormattedText] | None = None,
) -> Layout:
    title_bar_text = HTML(
        f" <style bg='ansipurple' color='white'><b> {title} </b></style> "
        f"<style color='#888888'>| {jargon}</style>"
    )

    # Sub-agent activity panel: one line per running delegate, just above the
    # status bar. ConditionalContainer collapses it to nothing when idle.
    extra_children = []
    if agent_activity_text is not None:
        extra_children.append(
            ConditionalContainer(
                Window(
                    content=FormattedTextControl(agent_activity_text),
                    dont_extend_height=True,
                    style="class:bottom-toolbar",
                ),
                filter=Condition(lambda: bool(agent_activity_text())),
            )
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
                    Window(height=1),  # Top margin for chat history
                    # Chat History
                    output_field,
                    # Input Area with frame (centered title) - with padding
                    Window(height=1),  # Top margin
                    Frame(
                        input_field,
                        title="Ctrl+J newline · Ctrl+V/Alt+V paste · ESC cancel · /help",
                        style="class:input-frame",
                    ),
                    Window(height=1),  # Bottom padding
                    # Sub-agent activity panel (collapses when idle)
                    *extra_children,
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
                *(extra_floats or []),
            ],
        ),
        focused_element=input_field,
    )
