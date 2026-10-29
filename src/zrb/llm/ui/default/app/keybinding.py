import string
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prompt_toolkit.filters import Filter
    from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
    from prompt_toolkit.widgets import TextArea

    from zrb.llm.ui.default.selection import UISelection

# Rows PageUp/PageDown leave in view from the previous screen, so the reader
# keeps a line or two to orient on.
PAGE_OVERLAP_ROWS = 4


def create_output_keybindings(
    input_field: "TextArea",
    choice: "UISelection | None" = None,
    output_field: "TextArea | None" = None,
) -> "KeyBindings":
    # lazy: heavy third-party
    from prompt_toolkit.application import get_app
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.key_binding import KeyBindings

    is_choice_active = Condition(
        lambda: choice is not None and choice.has_active_choice()
    )
    not_choice_active = ~is_choice_active
    kb = KeyBindings()

    @kb.add("escape", filter=not_choice_active)
    def _(event):
        get_app().layout.focus(input_field)

    @kb.add("up", filter=not_choice_active)
    def _(event):
        event.current_buffer.cursor_up()

    @kb.add("down", filter=not_choice_active)
    def _(event):
        event.current_buffer.cursor_down()

    # Paging always walks the transcript, whatever pane holds the focus and
    # even while a choice is active: a docked panel leaves the transcript
    # visible, and moving the option cursor is Up/Down's job, not PageUp's.
    @kb.add("pageup")
    def _(event):
        page_output(output_field, event, -1)

    @kb.add("pagedown")
    def _(event):
        page_output(output_field, event, 1)

    # Shift+Tab is left unbound so the app level can cycle modes.

    # Typing in the output pane moves to the input field, unless text is
    # selected (so it can be copied).
    def redirect_focus(event):
        if not event.current_buffer.selection_state:
            get_app().layout.focus(input_field)
            input_field.buffer.insert_text(event.data)

    for char in string.printable:
        if char in "\t\n\r\x0b\x0c":
            continue
        kb.add(char, filter=not_choice_active)(redirect_focus)

    bind_choice_navigation(kb, choice, is_choice_active)
    return kb


def page_output(
    output_field: "TextArea | None", event: "KeyPressEvent", direction: int
) -> None:
    """Move the transcript a screen at a time in *direction* (-1 up, 1 down).

    The pane is named rather than taken from `event.current_buffer`: PageUp
    pressed while a choice or a docked panel holds the focus has to scroll the
    transcript behind it, which is the one thing the user cannot otherwise do.
    The focused pane is only the fallback for a caller that has no transcript to
    name.
    """
    steps = max(1, event.app.output.get_size().rows - PAGE_OVERLAP_ROWS)
    buffer = (
        output_field.buffer if output_field is not None else event.current_buffer
    )
    if direction < 0:
        buffer.cursor_up(count=steps)
    else:
        buffer.cursor_down(count=steps)


def bind_choice_navigation(
    kb: "KeyBindings", choice: "UISelection | None", is_choice_active: "Filter"
) -> None:
    """Let Up/Down drive an active choice from a pane's own key bindings.

    Control-local bindings beat the app-level navigation bindings.
    """

    @kb.add("up", filter=is_choice_active)
    def _(event):
        if choice is not None:
            choice.move_choice_cursor(-1)

    @kb.add("down", filter=is_choice_active)
    def _(event):
        if choice is not None:
            choice.move_choice_cursor(1)
