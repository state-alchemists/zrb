"""The output stream zrb plays speech through, as far as it uses one.

`sounddevice`'s `OutputStream` is what opens here; naming the part of it the
player asks for keeps the player typed without holding PortAudio's module in
an annotation.
"""

from __future__ import annotations

from typing import Protocol


class AnyOutputStream(Protocol):
    """An output stream: start it, stop it when the sentence ends, close it."""

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...
