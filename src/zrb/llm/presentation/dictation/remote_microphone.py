"""The page's microphone, read off the face server as the cutter's blocks.

`RemoteMicrophone` stands in for the sounddevice input stream `listen` would
otherwise open: the same callback, the same blocks — mono float32 at the
transcriber's rate — and `active` and `close` beside them. One long GET
/audio/in arrives on a thread of its own and is handed on a block at a time, so
nothing else in dictation knows the microphone is not on this machine.

Echo cancelling is the browser's: the phone asks `getUserMedia` for it, which
cancels the page's own speaker out of what it hears. Nothing here opens the
local canceller, and none is imitated.
"""

from __future__ import annotations

import http.client
import logging
import threading
import urllib.request
from types import ModuleType
from typing import TYPE_CHECKING

from zrb.llm.presentation.dictation.echo_cancel import AudioCallback, Rechunker
from zrb.llm.contracts.util.face_server import (
    AUDIO_SAMPLE_WIDTH,
    MICROPHONE_PATH,
    check_audio_format,
)

if TYPE_CHECKING:
    import numpy
    from numpy.typing import NDArray

    Samples = NDArray[numpy.float32]

logger = logging.getLogger(__name__)

# Bytes asked of the socket at a time. `read1` answers with what has arrived
# rather than waiting for this much, so it bounds one read, not a block — which
# matters while nothing is being said: the server keeps a silent route alive
# with one frame of silence about every 15 seconds, and a read that insisted on
# a whole block would wait minutes for it.
_READ_BYTES = 4096
# How long closing the route may take. The reading thread is already ending,
# and a page that went away must not hold the session's teardown.
_CLOSE_JOIN_SECONDS = 1.0
# One step a 16-bit sample has on each side of zero: what a float sample of the
# same audio is a fraction of.
_INT16_SCALE = 32768.0


class RemoteMicrophone:
    """The page's microphone: GET /audio/in, handed on as sounddevice blocks.

    *callback* is called from the reading thread as sounddevice calls an input
    stream's: ``callback(indata, frames, time_info, status)``, *indata* a
    ``(blocksize, 1)`` float32 array at *samplerate*, and the last two ``None``.
    *url* is the face server, *headers* travel with the request, and *timeout*
    is how long a route may go quiet before it is taken for gone.

    A route that ends — the page was closed, the server stopped, the socket
    failed — leaves `active` false, which is what `listen` reopens from, the
    same way it reopens a stream PortAudio stopped.
    """

    def __init__(
        self,
        np: ModuleType,
        callback: AudioCallback,
        url: str,
        headers: dict[str, str],
        samplerate: int,
        blocksize: int,
        timeout: float,
    ) -> None:
        self._np = np
        self._callback = callback
        self._url = url
        self._headers = headers
        self._samplerate = samplerate
        self._timeout = timeout
        self._rechunker = Rechunker(np, max(1, blocksize), self._emit)
        # The response once opened, and the thread reading it.
        self._response: http.client.HTTPResponse | None = None
        self._thread: threading.Thread | None = None
        self._is_active = threading.Event()
        # Half a sample a read can leave over: nothing frames the body at a
        # sample boundary, so a sample may arrive split down the middle.
        self._pending = b""

    @property
    def is_active(self) -> bool:
        """Whether audio is still arriving, as sounddevice's `active` says a
        running stream is."""
        return self._is_active.is_set()

    # sounddevice's name for it, which `listen` reads of either microphone.
    active = is_active

    def start(self) -> None:
        """Open the route and start reading it, or raise `RuntimeError`."""
        try:
            self._response = open_audio_in(self._url, self._headers, self._timeout)
        except Exception as e:
            raise RuntimeError(
                f"Cannot reach the page's microphone at {self._url}"
                f"{MICROPHONE_PATH}: {e}"
            ) from e
        check_audio_format(self._response.headers, self._samplerate)
        self._is_active.set()
        self._thread = threading.Thread(
            target=self._read, name="zrb-remote-microphone", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        """Stop reading and let the route go, or raise `RuntimeError` saying
        why closing it failed (it is closed all the same)."""
        self._is_active.clear()
        response, self._response = self._response, None
        try:
            if response is not None:
                response.close()
        except OSError as e:
            raise RuntimeError(
                f"Closing the page's microphone at {self._url} failed: {e}"
            ) from e
        finally:
            thread = self._thread
            if thread is not None:
                thread.join(_CLOSE_JOIN_SECONDS)

    def _read(self) -> None:
        """Read the route to its end, handing blocks on as they arrive.

        A quiet socket is not on its own a gone page: the server says so with a
        frame of silence every 15 seconds. So a read that raises is taken for a
        route that is gone, and said once — by then `active` is false and
        `listen` is about to open a new one.
        """
        try:
            while self._is_active.is_set():
                data = self._read_once()
                if not data:
                    break
                self._rechunker.append(self._to_samples(data))
        except (OSError, http.client.HTTPException, ValueError) as e:
            logger.warning(f"The page's microphone stopped: {e}")
        finally:
            self._is_active.clear()

    def _read_once(self) -> bytes:
        """Whatever has arrived of the body, or ``b""`` at its end."""
        response = self._response
        if response is None:
            return b""
        return response.read1(_READ_BYTES)

    def _to_samples(self, data: bytes) -> "Samples":
        """*data* as float32 samples, holding half a sample back for the read
        that completes it."""
        np = self._np
        pending = self._pending + data
        whole = len(pending) - len(pending) % AUDIO_SAMPLE_WIDTH
        self._pending = pending[whole:]
        return (
            np.frombuffer(pending[:whole], np.int16).astype(np.float32) / _INT16_SCALE
        )

    def _emit(self, block: "Samples") -> None:
        self._callback(block.reshape(-1, 1), len(block), None, None)


def open_audio_in(
    url: str, headers: dict[str, str], timeout: float
) -> http.client.HTTPResponse:
    """The microphone route, open: one long response, no length, no framing."""
    request = urllib.request.Request(f"{url}{MICROPHONE_PATH}", headers=headers)
    return urllib.request.urlopen(request, timeout=timeout)
