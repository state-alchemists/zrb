from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AnyEchoCanceller(ABC):
    """Removes zrb's own voice from what the microphone hears, so the user
    can talk over zrb on speakers (barge-in).

    `process` takes each microphone block with the audio zrb played at the
    same moment (`zrb.llm.speech.echo_reference`), both float32 mono at
    16 kHz, and returns the microphone block with that echo taken out. It is
    called for every block, in order, while barge-in is on.
    """

    @property
    def name(self) -> str:
        """How the canceller is called in messages."""
        return type(self).__name__

    @property
    def needs_reference(self) -> bool:
        """Whether it works from the audio zrb played. One that does not
        (``none``) trusts the microphone not to hear zrb at all."""
        return True

    @property
    def is_converged(self) -> bool:
        """Whether it has learned the room well enough that what is left of
        zrb's voice is not mistaken for the user. Until then the microphone
        stays deaf while zrb speaks."""
        return True

    def reset(self) -> None:
        """Forget what it learned: the echo path changed (another output
        device). Nothing to forget by default."""

    @abstractmethod
    def process(self, mic: Any, far: Any) -> Any:
        """*mic* with the echo of *far* removed: a float32 array of the same
        length."""
