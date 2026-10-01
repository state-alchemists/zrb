from __future__ import annotations

from abc import ABC, abstractmethod


class AnyTranscriptionStream(ABC):
    """One utterance being transcribed while it is spoken.

    Dictation feeds it the utterance's audio a block at a time, reads
    `partial` to see where the speech is going, and calls `finish` when the
    utterance ends; the transcript is then mostly done already. A stream that
    is abandoned (the utterance was a cough) is closed instead.
    """

    @abstractmethod
    async def feed(self, audio: bytes) -> None:
        """Take the next *audio*: 16 kHz mono 16-bit PCM."""

    @property
    @abstractmethod
    def partial(self) -> str:
        """The transcript so far; it may still change."""

    @abstractmethod
    async def finish(self) -> str:
        """The utterance's final transcript. The stream is done after this."""

    async def close(self) -> None:
        """Abandon the stream without a transcript. Nothing to do by default."""
