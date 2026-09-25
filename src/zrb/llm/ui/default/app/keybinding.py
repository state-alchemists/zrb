import string
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prompt_toolkit.filters import Filter
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.widgets import TextArea

    from zrb.llm.ui.default.selection import UISelection


def create_output_keybindings(
    input_field: "TextArea",
    choice: "UISelection | None" = None,
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

    @kb.add("pageup", filter=not_choice_active)
    def _(event):
        event.current_buffer.cursor_up(count=event.app.output.get_size().rows - 4)

    # Shift+Tab is left unbound so the app level can cycle modes (ADR-0075).

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
