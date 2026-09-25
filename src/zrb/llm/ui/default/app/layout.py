from typing import TYPE_CHECKING, Any, Callable, cast

from prompt_toolkit.filters import Condition, has_completions, has_selection
from prompt_toolkit.formatted_text import HTML, AnyFormattedText
from prompt_toolkit.history import History
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window, WindowAlign
from prompt_toolkit.layout.containers import ConditionalContainer, Float, FloatContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.widgets import Frame, TextArea

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.ui.default.app.completion import InputCompleter
from zrb.llm.ui.default.app.keybinding import (
    bind_choice_navigation,
    create_output_keybindings,
)
from zrb.llm.ui.ui_config import UIConfig

if TYPE_CHECKING:
    from zrb.llm.ui.default.selection import UISelection


def create_input_field(  # noqa: C901 -- registration/factory fn; mccabe sums nested handlers into this line, radon scores each separately (near-trivial on its own)
    history_manager: AnyHistoryManager,
    ui_config: UIConfig,
    custom_commands: list[AnyCustomCommand] | None = None,
    history: History | None = None,
    custom_model_names: list[str] | None = None,
    up_arrow_handler: Callable[[Any], bool] | None = None,
    down_arrow_handler: Callable[[Any], bool] | None = None,
    recall_active: Callable[[], bool] | None = None,
    choice: "UISelection | None" = None,
) -> TextArea:
    @Condition
    def is_choice_active() -> bool:
        return choice is not None and choice.has_active_choice()

    class DynamicHeightTextArea(TextArea):
        def __init__(self, *args, **kwargs):
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
            text = self.text
            line_count = text.count("\n") + 1

            if wrap_lines and width > 0:
                wrapped_lines = 0
                for line in text.split("\n"):
                    wrapped_lines += (
                        (len(line) + width - 1) // width if len(line) > 0 else 1
                    )
                line_count = max(line_count, wrapped_lines)

            return min(max(line_count, 1), 10)

    text_area = DynamicHeightTextArea(
        multiline=True,
        wrap_lines=True,
        history=history,
        completer=InputCompleter(
            history_manager=history_manager,
            ui_config=ui_config,
            custom_commands=custom_commands,
            custom_model_names=custom_model_names,
        ),
        complete_while_typing=True,
        focus_on_click=~is_choice_active,
        read_only=is_choice_active,
        style="class:input_field",
        dont_extend_height=True,
    )

    # TextArea takes no key_bindings argument; attach them to its control.
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

    @Condition
    def is_recall_active() -> bool:
        # An untouched multi-line recall still lets Up walk the queue.
        return recall_active is not None and recall_active()

    # Up/Down recall history at the first/last line; the queued-message
    # handlers (UIMessageEditing) win when they consume the keypress.
    @kb.add(
        "up",
        filter=(is_first_line | is_recall_active)
        & ~has_selection
        & ~has_completions
        & ~is_choice_active,
    )
    def _(event):
        if up_arrow_handler is not None and up_arrow_handler(event):
            return
        event.current_buffer.history_backward()

    @kb.add(
        "down",
        filter=is_last_line & ~has_selection & ~has_completions & ~is_choice_active,
    )
    def _(event):
        if down_arrow_handler is not None and down_arrow_handler(event):
            return
        event.current_buffer.history_forward()

    bind_choice_navigation(kb, choice, is_choice_active)

    # Shift+Tab is deliberately unbound so the app level can cycle modes
    # (ADR-0075).
    return text_area


def create_output_field(
    greeting: str,
    lexer: Lexer,
    key_bindings: KeyBindings | None = None,
    input_field: "TextArea | None" = None,
    choice: "UISelection | None" = None,
) -> TextArea:
    def get_line_prefix(line_number: int, wrap_number: int) -> AnyFormattedText:
        return " "

    # An empty greeting adds no padding: the default UI appends its own
    # re-renderable greeting panel afterwards.
    initial_text = greeting.rstrip() + "\n\n" if greeting.strip() != "" else ""
    text_area = TextArea(
        text=initial_text,
        read_only=True,
        scrollbar=False,
        wrap_lines=True,
        lexer=lexer,
        focus_on_click=True,
        focusable=True,
        get_line_prefix=get_line_prefix,
        style="class:output_field",
        dont_extend_height=False,
    )
    if key_bindings is None and input_field is not None:
        key_bindings = create_output_keybindings(input_field, choice)
    if key_bindings is not None:
        text_area.control.key_bindings = key_bindings

    _bind_scroll_to_cursor(text_area)

    text_area.buffer.cursor_position = len(text_area.text)
    return text_area


def _bind_scroll_to_cursor(text_area: TextArea, lines: int = 3) -> None:
    """Make the mouse wheel move the output cursor instead of the viewport.

    The window pins itself to the cursor, so nudging `vertical_scroll` would
    snap back on the next streamed chunk. Moving the cursor scrolls for real
    and, leaving the last line, pauses auto-follow. Works whichever pane has
    focus.
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
        " <title-text><b> {} </b></title-text> <faint>| {}</faint>"
    ).format(title, jargon)

    # Sub-agent activity panel above the status bar, collapsed when idle. The
    # filter reuses the session-scoped callable; an unscoped registry read
    # would react to every session's activity.
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
                    Window(
                        height=2,
                        content=FormattedTextControl(title_bar_text),
                        style="class:title-bar",
                        align=WindowAlign.CENTER,
                    ),
                    Window(
                        height=3,
                        content=FormattedTextControl(info_bar_text),
                        style="class:info-bar",
                    ),
                    Window(height=1),
                    output_field,
                    Window(height=1),
                    Frame(
                        input_field,
                        title="Ctrl+J newline · Ctrl+V/Alt+V paste · ESC cancel",
                        style="class:input-frame",
                    ),
                    # A Frame title is one line, too narrow for every hint.
                    Window(
                        height=1,
                        content=FormattedTextControl(
                            HTML("<faint> Ctrl+O expand/collapse · /help</faint>")
                        ),
                        align=WindowAlign.CENTER,
                    ),
                    *extra_children,
                    Window(
                        height=2,
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
