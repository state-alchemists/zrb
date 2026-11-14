"""Opening the microphone: which device, echo cancellation, and what to say
when one will not start.

`listen` and `record` decide what to do with the audio; this module gets it.
It is the only place in dictation that touches PortAudio: `import_audio` brings
numpy and `sounddevice` in (both are the `zrb[voice]` extra, so the import is
lazy), `to_device` turns the device setting into what PortAudio takes, and
`open_microphone` opens a stream with the retry and the fallback a real sound
card needs. `close_microphone` closes one off the event loop, because closing
can block.

The failure messages live here too: they are about a device, and the person who
reads one is the person whose microphone did not open.
"""

from __future__ import annotations

import asyncio
import logging
from functools import cache, partial
from typing import Any, Callable

from zrb.config.config import CFG
from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.echo_cancel import (
    EchoCancelledMicrophone,
    get_unavailable_reason,
)
from zrb.llm.util.portaudio_exit import guard_portaudio_exit
from zrb.llm.util.teardown import close_quietly
from zrb.util.async_thread import run_in_daemon

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # what the transcribers expect
# Retry count and delay for PortAudio's one-second ALSA startup deadline.
_OPEN_ATTEMPTS = 3
_OPEN_RETRY_SECONDS = 0.5
# How long the echo-cancelled microphone has to deliver its first block.
_ECHO_CANCEL_FIRST_AUDIO_SECONDS = 2.0


def import_audio() -> tuple[Any, Any]:
    """numpy and sounddevice, or a `RuntimeError` saying how to install them."""
    try:
        # lazy: heavy third-party (numpy/sounddevice are zrb[voice] extras)
        import numpy as np
        import sounddevice as sd
    except (ImportError, OSError) as e:
        raise RuntimeError(
            f"Dictation needs the zrb[voice] extra ({e}): pip install 'zrb[voice]'"
        ) from e
    guard_portaudio_exit(sd)
    return np, sd


def to_device(device: "str | int | None") -> "int | str | None":
    """A device setting as `sounddevice` takes it: a digit string is an index.

    `sounddevice` reads an `int` as a device index and a `str` as a name to
    match, so "2" has to become ``2``. A non-numeric value passes through as a
    name, and empty or unset is PortAudio's own default.
    """
    if device is None or isinstance(device, int):
        return device
    text = device.strip()
    if not text:
        return None
    return int(text) if text.isdigit() else text


async def open_microphone(
    sd: Any,
    on_audio: Callable[..., None],
    device: "str | int | None" = None,
    is_echo_cancelled: bool = False,
    **options: Any,
) -> Any:
    """The microphone, open and running, or a `RuntimeError` saying why.

    With *is_echo_cancelled*, it opens through macOS voice processing
    (`EchoCancelledMicrophone`, which needs ``blocksize`` among *options*);
    when that will not start, the plain PortAudio one opens instead, so a
    broken one never costs the user their microphone.

    PortAudio gives the ALSA thread it starts one second to come up and reports
    ``paTimedOut`` when it misses: a WSL2 VM stalling on I/O misses it, for
    reasons that have nothing to do with zrb, and the stall is over by the time
    the call returns. So a start that fails is tried again, and only the last
    failure is raised. A stream that never started is closed first, best-effort,
    so the next try does not contend with it for the device.

    A failure to construct the stream (no such device, PortAudio missing) is
    not retried.
    """
    if is_echo_cancelled:
        microphone = await _start_echo_cancelled_microphone(
            on_audio, options["blocksize"]
        )
        if microphone is not None:
            return microphone
    device = to_device(device)

    def start():
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=on_audio,
                device=device,
                **options,
            )
        except Exception as e:
            raise RuntimeError(
                f"Cannot open microphone: {e}. Check permissions and that no "
                "other app is using the mic."
            ) from e
        try:
            stream.start()
        except Exception as e:
            raise _NotStarted(stream.close, e) from e
        return stream

    def start_or_not_started():
        # Return the failure instead of raising it, so one that lands after
        # cancellation still reaches `on_orphan` and gets closed.
        try:
            return start()
        except _NotStarted as e:
            return e

    attempt = 0
    while True:
        attempt += 1
        # Open off the event loop: opening can stall for seconds (see WSL2
        # above), and Ctrl+C cannot cancel a blocked loop.
        opened = await run_in_daemon(
            start_or_not_started, name="zrb-microphone", on_orphan=lambda s: s.close()
        )
        if not isinstance(opened, _NotStarted):
            return opened
        await close_microphone(opened.close, "the microphone that would not start")
        if attempt >= _OPEN_ATTEMPTS:
            raise RuntimeError(
                _microphone_failure_message(device, opened.cause)
            ) from opened
        logger.warning(f"Starting the microphone failed ({opened.cause}); trying again")
        await asyncio.sleep(_OPEN_RETRY_SECONDS)


async def close_microphone(close: Callable[[], object], what: str) -> None:
    """`close_quietly`, with *close* run off the event loop.

    Stopping a stream can block, and the echo-cancelled one waits on Core Audio
    to switch voice processing off; on the loop that freezes the UI and a
    Ctrl+C lands inside the native call, where it escapes as a
    `KeyboardInterrupt`. Opening is off the loop for the same reason.
    """
    await close_quietly(
        partial(run_in_daemon, close, name="zrb-microphone-close"), what
    )


class _NotStarted(Exception):
    """A stream that was created but failed to start; *close* closes it."""

    def __init__(self, close: Callable[[], None], cause: Exception) -> None:
        super().__init__(str(cause))
        self.close = close
        self.cause = cause


def is_echo_cancelled_stream(stream: object) -> bool:
    """Whether *stream* came from macOS voice processing.

    `listen` asks this when a stream dies. A voice-processed one is not reopened
    as it was: it died on a route change, and reopening it would die the same
    way over and over, so that listening carries on without echo cancellation.
    """
    return isinstance(stream, EchoCancelledMicrophone)


def is_echo_cancel_usable(config: DictationConfig) -> bool:
    """Whether *config* asks for echo cancellation and this machine can give
    it; when it asks and cannot, says why once."""
    if not config.is_echo_cancel_enabled:
        return False
    reason = get_unavailable_reason(config.device)
    if reason is not None:
        _warn_once(f"Echo cancellation is off: {reason}")
    return reason is None


@cache
def _warn_once(message: str) -> None:
    """Log *message* the first time only; push-to-talk opens the microphone
    on every press."""
    logger.warning(message)


async def _start_echo_cancelled_microphone(
    on_audio: Callable[..., None], blocksize: int
) -> EchoCancelledMicrophone | None:
    """The microphone through macOS voice processing, hearing, or ``None``
    (and a warning saying why) when it will not start or hears nothing."""
    np, _ = import_audio()
    microphone = EchoCancelledMicrophone(np, on_audio, SAMPLE_RATE, blocksize)
    try:
        microphone.start()
        await microphone.confirm_audio(_ECHO_CANCEL_FIRST_AUDIO_SECONDS)
    except RuntimeError as e:
        logger.warning(f"{e}; using the microphone without echo cancellation")
        try:
            microphone.close()
        except RuntimeError as close_error:
            logger.warning(f"{close_error}; opening the plain microphone anyway")
        return None
    return microphone


def _microphone_failure_message(device: "int | str | None", error: Exception) -> str:
    """What to say when the microphone will not start.

    Names the device PortAudio was asked for — ``None`` is its own default, what
    ``sd.default.device`` resolves to — and the setting that names another,
    because which device a Linux or WSL machine opens is the usual difference
    between a microphone that works and one that does not.
    """
    return (
        f"Cannot open microphone: {error}. PortAudio was asked for device "
        f"{device!r} (None: its own default). Check permissions and that no other "
        f"app is using the mic, and set {CFG.ENV_PREFIX}_LLM_DICTATION_DEVICE to "
        "name another one."
    )
