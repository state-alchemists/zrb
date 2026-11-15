"""The face server's two audio routes: the page's microphone, and its speaker.

With `LLM_VOICE_REMOTE_URL` set, zrb's voice moves into the page that server
serves: dictation reads the microphone from GET /audio/in, and the speech player
writes what zrb says to POST /say. The machine that runs zrb then opens neither
a microphone nor an output stream, and a phone across the room holds both. Empty
— how it ships — leaves each of them where it was, on this machine.

Both routes carry the same audio, and the contract is spelled here once because
two packages speak it: raw little-endian signed 16-bit mono PCM at one rate,
named in headers rather than wrapped in a container, since neither side
converts, mixes or resamples.
"""

from __future__ import annotations

from email.message import Message

from zrb.config.config import CFG

# What both routes carry: two bytes a sample, one channel. zrb neither converts
# nor mixes, so a route that names anything else is refused rather than fed to
# the cutter or the player as though it were this.
AUDIO_SAMPLE_WIDTH = 2
AUDIO_CHANNELS = 1

# The headers that name the format, and where each route lives on the server.
SAMPLE_RATE_HEADER = "X-Sample-Rate"
SAMPLE_WIDTH_HEADER = "X-Sample-Width"
CHANNELS_HEADER = "X-Channels"
MICROPHONE_PATH = "/audio/in"
SPEAKER_PATH = "/say"


def get_remote_url() -> str | None:
    """The face server's base URL, or ``None`` while the voice stays here."""
    return CFG.LLM_VOICE_REMOTE_URL.strip().rstrip("/") or None


def is_remote_voice_selected() -> bool:
    """Whether this session's microphone and speaker are both the page's."""
    return get_remote_url() is not None


def get_remote_headers() -> dict[str, str]:
    """The header the server's routes want, when it holds a token at all."""
    token = CFG.LLM_VOICE_REMOTE_TOKEN.strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def check_audio_format(headers: Message, expected_rate: int) -> None:
    """Refuse a microphone body zrb cannot read, saying what was sent instead.

    The body is one long response of samples with no framing of its own, so
    these three headers are the only thing that says what the bytes mean. A
    rate other than *expected_rate* is a voice heard at the wrong speed, and a
    wider sample or a second channel is not what the cutter is fed.
    """
    rate = _read_header_int(headers, SAMPLE_RATE_HEADER)
    width = _read_header_int(headers, SAMPLE_WIDTH_HEADER)
    channels = _read_header_int(headers, CHANNELS_HEADER)
    if (rate, width, channels) != (expected_rate, AUDIO_SAMPLE_WIDTH, AUDIO_CHANNELS):
        raise RuntimeError(
            f"The face server's microphone sends {rate} Hz, {width} byte(s) a "
            f"sample and {channels} channel(s); dictation reads {expected_rate} "
            f"Hz, {AUDIO_SAMPLE_WIDTH} bytes a sample and {AUDIO_CHANNELS} "
            "channel, and resamples nothing."
        )


def _read_header_int(headers: Message, name: str) -> int:
    """*name* from *headers* as a number, or a `RuntimeError` naming it."""
    raw = headers.get(name) or ""
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise RuntimeError(
            f"The face server's microphone sent no usable {name} ({raw!r}); "
            "its routes carry raw 16-bit mono PCM and name the format in "
            f"{SAMPLE_RATE_HEADER}, {SAMPLE_WIDTH_HEADER} and {CHANNELS_HEADER}."
        ) from None
