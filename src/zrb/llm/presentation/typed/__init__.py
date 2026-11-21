"""A text box on the page as chat input.

`enable_typed_input` turns a line typed on the face page into a user turn, read
from the same server that holds the page's microphone and camera.
"""

from zrb.llm.presentation.typed.feature import enable_typed_input
from zrb.llm.presentation.typed.remote_typed import RemoteTyped, open_typed_in

__all__ = ["RemoteTyped", "enable_typed_input", "open_typed_in"]
