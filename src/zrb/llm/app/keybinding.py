import string

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import has_completions
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.widgets import TextArea


def create_output_keybindings(input_field: TextArea) -> KeyBindings:
    kb = KeyBindings()

    @kb.add("escape")
    def _(event):
        get_app().layout.focus(input_field)

    @kb.add("c-v")
    @kb.add("escape", "v")
    def _(event):
        # Paste clipboard data to input field
        get_app().layout.focus(input_field)
        if event.app.clipboard:
            input_field.buffer.paste_clipboard_data(event.app.clipboard.get_data())

    # Scrolling and navigation
    @kb.add("up")
    def _(event):
        event.current_buffer.cursor_up()

    @kb.add("down")
    def _(event):
        event.current_buffer.cursor_down()

    @kb.add("pageup")
    def _(event):
        event.current_buffer.cursor_up(count=event.app.output.get_size().rows - 4)

    @kb.add("pagedown")
    def _(event):
        event.current_buffer.cursor_down(count=event.app.output.get_size().rows - 4)

    # Tab navigation
    @kb.add("tab", filter=~has_completions)
    def _(event):
        event.app.layout.focus_next()

    @kb.add("s-tab", filter=~has_completions)
    def _(event):
        event.app.layout.focus_previous()

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
        kb.add(char)(redirect_focus)

    return kb
