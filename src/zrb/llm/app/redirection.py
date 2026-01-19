import io
import sys


class StreamToUI(io.TextIOBase):
    """Redirect stdout to UI's append_to_output."""

    def __init__(self, ui_callback):
        self.ui_callback = ui_callback
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self._is_first_write = True

    def write(self, text: str) -> int:
        from prompt_toolkit.application import get_app

        text = text.expandtabs(4)
        if text:
            if self._is_first_write:
                self.ui_callback("\n", end="")
                self._is_first_write = False
            self.ui_callback(text, end="")
            get_app().invalidate()
        return len(text)

    def flush(self):
        self.original_stdout.flush()
        self.original_stderr.flush()
