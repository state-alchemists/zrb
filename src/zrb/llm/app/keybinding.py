import string

from prompt_toolkit.application import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.widgets import TextArea


def create_output_keybindings(input_field: TextArea) -> KeyBindings:
    kb = KeyBindings()

    @kb.add("escape")
    def _(event):
        get_app().layout.focus(input_field)

    @kb.add("c-c")
    def _(event):
        # Copy selection to clipboard
        if event.current_buffer.selection_state:
            data = event.current_buffer.copy_selection()
            event.app.clipboard.set_data(data)
        get_app().layout.focus(input_field)

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
