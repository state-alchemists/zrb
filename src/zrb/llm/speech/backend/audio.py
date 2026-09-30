"""Synthesized speech as raw audio, for zrb to play itself.

A backend that can render speech (rather than play it through a program of
its own) returns a `SpeechAudio`: 16-bit mono PCM, its sample rate, and its
chunks, read as they arrive so a streamed download starts playing early.
zrb playing the audio is what lets dictation cancel zrb's own voice out of
the microphone (it knows every sample it plays) and pause it mid-sentence.
"""

from __future__ import annotations

import io
import struct
import wave
from collections.abc import Callable, Iterable, Iterator
from typing import BinaryIO

_CHUNK_BYTES = 4096


class SpeechAudio:
    """16-bit mono PCM at *sample_rate*, in *chunks*; *close* releases what
    produces them (a download) and ends a read blocked on it."""

    def __init__(
        self,
        sample_rate: int,
        chunks: Iterable[bytes],
        close: Callable[[], None] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunks = chunks
        self._close = close

    def close(self) -> None:
        if self._close is not None:
            self._close()


def create_wav_audio(wav_bytes: bytes) -> SpeechAudio:
    """*wav_bytes* (a whole 16-bit mono WAV file) as `SpeechAudio`."""
    with wave.open(io.BytesIO(wav_bytes)) as wav:
        if wav.getsampwidth() != 2 or wav.getnchannels() != 1:
            raise RuntimeError(_unplayable("must be 16-bit mono"))
        return SpeechAudio(wav.getframerate(), [wav.readframes(wav.getnframes())])


def create_streamed_wav_audio(
    source: BinaryIO, close: Callable[[], None] | None = None
) -> SpeechAudio:
    """The WAV read from *source* as `SpeechAudio`, its samples yielded as
    they arrive. A streamed WAV's sizes are placeholders, so the header is
    read chunk by chunk up to ``data``, and the samples run to the end of
    the stream."""
    sample_rate = _read_wav_header(source)
    return SpeechAudio(sample_rate, _read_chunks(source), close or source.close)


def _read_wav_header(source: BinaryIO) -> int:
    riff = _read_exactly(source, 12)
    if riff[:4] != b"RIFF" or riff[8:12] != b"WAVE":
        raise RuntimeError(_unplayable("is not a WAV stream"))
    sample_rate = 0
    while True:
        chunk_id, size = struct.unpack("<4sI", _read_exactly(source, 8))
        if chunk_id == b"data":
            if not sample_rate:
                raise RuntimeError(_unplayable("has no format chunk"))
            return sample_rate
        body = _read_exactly(source, size + (size & 1))
        if chunk_id == b"fmt ":
            _, channels, sample_rate, _, _, bits = struct.unpack("<HHIIHH", body[:16])
            if channels != 1 or bits != 16:
                raise RuntimeError(_unplayable("must be 16-bit mono"))


def _read_exactly(source: BinaryIO, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = source.read(size - len(data))
        if not chunk:
            raise RuntimeError(_unplayable("ended inside its header"))
        data += chunk
    return data


def _unplayable(problem: str) -> str:
    return (
        f"The speech backend's audio {problem}, so zrb cannot play it itself; "
        "set ZRB_LLM_SPEECH_PLAYER=command to use a player program."
    )


def _read_chunks(source: BinaryIO) -> Iterator[bytes]:
    left = b""
    while chunk := source.read(_CHUNK_BYTES):
        chunk = left + chunk
        # Whole samples only: a read can end between a sample's two bytes.
        cut = len(chunk) - (len(chunk) % 2)
        left = chunk[cut:]
        if cut:
            yield chunk[:cut]
