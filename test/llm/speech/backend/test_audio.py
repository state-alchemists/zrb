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


def _format_chunk(audio_format=1, channels=1, bits=16, extra=b""):
    body = struct.pack("<HHIIHH", audio_format, channels, 24000, 48000, 2, bits) + extra
    return b"fmt " + struct.pack("<I", len(body)) + body


def _wav_with(fmt: bytes, pcm=b"\x01\x00") -> bytes:
    return b"RIFF\xff\xff\xff\xffWAVE" + fmt + b"data\xff\xff\xff\xff" + pcm


def _extensible(sub_format):
    # cbSize 22, valid bits, channel mask, then the sub-format GUID.
    return struct.pack("<HHI", 22, 16, 4) + struct.pack("<H", sub_format) + b"\x00" * 14


def test_compressed_audio_is_refused_not_played_as_noise():
    with pytest.raises(RuntimeError, match="not uncompressed PCM"):
        create_streamed_wav_audio(io.BytesIO(_wav_with(_format_chunk(audio_format=2))))


def test_extensible_pcm_is_accepted_and_extensible_other_refused():
    pcm = _format_chunk(audio_format=0xFFFE, extra=_extensible(1))
    assert create_streamed_wav_audio(io.BytesIO(_wav_with(pcm))).sample_rate == 24000
    float_audio = _format_chunk(audio_format=0xFFFE, extra=_extensible(3))
    with pytest.raises(RuntimeError, match="not uncompressed PCM"):
        create_streamed_wav_audio(io.BytesIO(_wav_with(float_audio)))


def test_a_short_format_chunk_is_refused():
    fmt = b"fmt " + struct.pack("<I", 8) + b"\x01\x00" * 4
    with pytest.raises(RuntimeError, match="broken format chunk"):
        create_streamed_wav_audio(io.BytesIO(_wav_with(fmt)))


def test_a_header_claiming_gigabytes_is_refused_before_reading_it():
    header = b"RIFF\xff\xff\xff\xffWAVE" + b"LIST" + struct.pack("<I", 2**31)
    source = io.BufferedReader(io.BytesIO(header))

    with pytest.raises(RuntimeError, match="header too large"):
        create_streamed_wav_audio(source)


def test_a_whole_file_that_is_not_pcm_is_refused():
    with pytest.raises(RuntimeError, match="not uncompressed PCM"):
        create_wav_audio(
            _wav_with(_format_chunk(audio_format=2))
            .replace(b"\xff\xff\xff\xff", b"\x2a\x00\x00\x00", 1)
            .replace(b"data\xff\xff\xff\xff", b"data\x02\x00\x00\x00")
        )


@pytest.mark.parametrize("rate", [0, 10, 10_000_000])
def test_a_streamed_wav_with_an_impossible_sample_rate_is_refused(rate):
    with pytest.raises(RuntimeError, match="sample rate"):
        create_streamed_wav_audio(io.BytesIO(_streamed(b"\x01\x00", rate=rate)))


@pytest.mark.parametrize("rate", [0, 10_000_000])
def test_a_whole_wav_file_with_an_impossible_sample_rate_is_refused(rate):
    wav = bytearray(_wav(b"\x01\x00"))
    wav[24:28] = struct.pack("<I", rate)  # the format chunk's sample rate
    with pytest.raises(RuntimeError, match="sample rate"):
        create_wav_audio(bytes(wav))
