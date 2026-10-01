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
# The header before the samples, all chunks together: a WAV's metadata is a
# few hundred bytes, and a stream that claims more (a hostile or broken
# server) must not make zrb read it into memory.
_MAX_HEADER_BYTES = 1 << 20
_PCM = 1
# Sample rates speech can have: a rate outside them is a broken or hostile
# header, and would open no output stream (0 also divides by zero when
# resampling for echo cancellation).
_MIN_SAMPLE_RATE = 1000
_MAX_SAMPLE_RATE = 384000
_EXTENSIBLE = 0xFFFE


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
    try:
        with wave.open(io.BytesIO(wav_bytes)) as wav:
            if wav.getsampwidth() != 2 or wav.getnchannels() != 1:
                raise RuntimeError(_unplayable("must be 16-bit mono"))
            sample_rate = _check_sample_rate(wav.getframerate())
            return SpeechAudio(sample_rate, [wav.readframes(wav.getnframes())])
    except wave.Error as exc:  # the module reads uncompressed PCM only
        raise RuntimeError(_unplayable(f"is not uncompressed PCM ({exc})")) from exc


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
    header_bytes = 12
    while True:
        chunk_id, size = struct.unpack("<4sI", _read_exactly(source, 8))
        if chunk_id == b"data":
            if not sample_rate:
                raise RuntimeError(_unplayable("has no format chunk"))
            return sample_rate
        header_bytes += 8 + size + (size & 1)
        if header_bytes > _MAX_HEADER_BYTES:
            raise RuntimeError(_unplayable("has a header too large to be speech"))
        body = _read_exactly(source, size + (size & 1))
        if chunk_id == b"fmt ":
            sample_rate = _read_format(body)


def _read_format(body: bytes) -> int:
    """The sample rate of a ``fmt `` chunk describing 16-bit mono PCM;
    anything else (compressed, A-law, stereo) would play as noise."""
    if len(body) < 16:
        raise RuntimeError(_unplayable("has a broken format chunk"))
    audio_format, channels, sample_rate, _, _, bits = struct.unpack(
        "<HHIIHH", body[:16]
    )
    if audio_format == _EXTENSIBLE and len(body) >= 26:
        # The real format is the first two bytes of the sub-format GUID.
        (audio_format,) = struct.unpack("<H", body[24:26])
    if audio_format != _PCM:
        raise RuntimeError(_unplayable("is not uncompressed PCM"))
    if channels != 1 or bits != 16:
        raise RuntimeError(_unplayable("must be 16-bit mono"))
    return _check_sample_rate(sample_rate)


def _check_sample_rate(sample_rate: int) -> int:
    if not _MIN_SAMPLE_RATE <= sample_rate <= _MAX_SAMPLE_RATE:
        raise RuntimeError(
            _unplayable(
                f"has a sample rate of {sample_rate} Hz, outside "
                f"{_MIN_SAMPLE_RATE}-{_MAX_SAMPLE_RATE}"
            )
        )
    return sample_rate


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
