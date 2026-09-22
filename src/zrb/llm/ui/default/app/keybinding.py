import string
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

    # Scrolling and navigation
    @kb.add("up", filter=not_choice_active)
    def _(event):
        event.current_buffer.cursor_up()

    @kb.add("down", filter=not_choice_active)
    def _(event):
        event.current_buffer.cursor_down()

    @kb.add("pageup", filter=not_choice_active)
    def _(event):
        event.current_buffer.cursor_up(count=event.app.output.get_size().rows - 4)

    # Focus traversal is handled by Tab at the app level; Shift+Tab is
    # intentionally not bound here so Shift+Tab can cycle modes at the app
    # level. Tab still drives completion-menu navigation when a menu is open
    # (the app-level binding is gated by ~has_completions). See ADR-0075.

    # Only redirect printable characters when output field is focused
    # and no text is selected (to allow copying)
    def redirect_focus(event):
        # Only redirect if no text is selected
        if not event.current_buffer.selection_state:
            get_app().layout.focus(input_field)
            input_field.buffer.insert_text(event.data)

    for char in string.printable:
        # Skip control characters (Tab, Newline, etc.)
        #  to preserve navigation/standard behavior
        if char in "\t\n\r\x0b\x0c":
            continue
        kb.add(char, filter=not_choice_active)(redirect_focus)

    # While a choice is active, Up/Down drive it from this pane: control-local
    # bindings beat the app-level navigation binding.
    @kb.add("up", filter=is_choice_active)
    def _(event):
        if choice is not None:
            choice.move_choice_cursor(-1)

    @kb.add("down", filter=is_choice_active)
    def _(event):
        if choice is not None:
            choice.move_choice_cursor(1)

    return kb
