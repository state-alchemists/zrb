"""`SpeechAudio` from a whole WAV file or a streamed one."""

import io
import struct
import wave

import pytest

from zrb.llm.speech.backend.audio import (
    SpeechAudio,
    create_streamed_wav_audio,
    create_wav_audio,
)


def _wav(pcm: bytes, rate=22050, channels=1, width=2) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def _streamed(pcm: bytes, rate=24000, extra: bytes = b"") -> bytes:
    """A streamed WAV: placeholder sizes, and any chunks before the data."""
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    return (
        b"RIFF\xff\xff\xff\xffWAVE"
        + b"fmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + extra
        + b"data\xff\xff\xff\xff"
        + pcm
    )


class Trickle(io.BytesIO):
    """Returns at most three bytes per read, as a slow socket can."""

    def read(self, size=-1):
        return super().read(3 if size < 0 else min(size, 3))


def test_a_whole_wav_file_becomes_one_chunk():
    audio = create_wav_audio(_wav(b"\x01\x00\x02\x00", rate=16000))
    assert audio.sample_rate == 16000
    assert list(audio.chunks) == [b"\x01\x00\x02\x00"]


def test_a_whole_wav_file_that_is_not_16_bit_mono_is_refused():
    with pytest.raises(RuntimeError, match="16-bit mono"):
        create_wav_audio(_wav(b"\x00" * 8, channels=2))


def test_a_streamed_wav_yields_whole_samples_as_they_arrive():
    pcm = bytes(range(20))
    extra = b"LIST" + struct.pack("<I", 3) + b"abc\x00"  # odd size, padded
    audio = create_streamed_wav_audio(Trickle(_streamed(pcm, extra=extra)))

    chunks = list(audio.chunks)

    assert audio.sample_rate == 24000
    assert b"".join(chunks) == pcm
    assert all(len(chunk) % 2 == 0 for chunk in chunks)


@pytest.mark.parametrize(
    "data, message",
    [
        (b"NOPE" * 3, "not a WAV"),
        (b"RIFF\x00\x00\x00\x00WAVE", "ended inside its header"),
        (b"RIFF\x00\x00\x00\x00WAVEdata\x00\x00\x00\x00", "no format chunk"),
        (
            b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
            + struct.pack("<HHIIHH", 1, 2, 8000, 32000, 4, 16),
            "16-bit mono",
        ),
    ],
)
def test_a_broken_streamed_wav_is_refused(data, message):
    with pytest.raises(RuntimeError, match=message):
        create_streamed_wav_audio(io.BytesIO(data))


def test_closing_audio_calls_its_close():
    closed = []
    SpeechAudio(8000, [], lambda: closed.append(True)).close()
    SpeechAudio(8000, []).close()
    assert closed == [True]
