"""The speech player's output stream, written to the face server's speaker.

`RemoteOutputStream` stands in for the sounddevice `OutputStream` the player
would otherwise open: `start`, `stop`, `close` and the same `active` word, with
the device's callback read on a thread of this stream's, one block at a time,
each posted to POST /say as it comes due. The blocks are paced by the clock, so
a sentence takes as long to say as it does through a speaker, and pausing,
stopping and the underrun count keep meaning there what they mean here.

Nothing here opens a device: where the page's speaker is selected, this is the
only place zrb's voice goes.
"""

from __future__ import annotations

import http.client
import logging
import threading
import time
import urllib.parse
from collections.abc import Callable

from zrb.llm.util.face_server import SAMPLE_RATE_HEADER, SPEAKER_PATH

logger = logging.getLogger(__name__)

# How long stopping may take. The writer is asleep between blocks and wakes on
# the stop, so this is a bound on a route that will not take its last chunk.
_STOP_JOIN_SECONDS = 1.0
# The zero-length chunk that ends a chunked body: a sentence stopped where it
# was is still a whole body, and the page plays what came.
_LAST_CHUNK = b"0\r\n\r\n"
# How much of a refusal's body is read before closing: enough for the route's
# own sentence saying what it would not take, and not a page of it.
_REFUSAL_BODY_BYTES = 512


class RemoteOutputStream:
    """The page's speaker: the player's blocks, posted as they come due.

    *read* is the device's callback, asked for *block_frames* samples as 16-bit
    PCM each time — what the player hands a sounddevice stream to fill. *url*
    is the face server, *headers* travel with the request, *sample_rate* is the
    rate the PCM is at (the route refuses one it cannot play), and *timeout*
    bounds the socket.

    A route that fails leaves `active` false and ends the sentence where it
    was, which is what the player reads of a device that stopped playing.
    """

    def __init__(
        self,
        read: Callable[[int], bytes],
        sample_rate: int,
        block_frames: int,
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> None:
        self._read = read
        self._sample_rate = sample_rate
        self._block_frames = max(1, block_frames)
        # How long one block plays, which is how far apart they are written.
        self._block_seconds = self._block_frames / sample_rate
        self._url = url
        self._headers = headers
        self._timeout = timeout
        # The connection once opened, and the thread writing it.
        self._connection: http.client.HTTPConnection | None = None
        self._thread: threading.Thread | None = None
        # Set by `stop`: the sentence is over, so the block after this one is
        # not written and the body is ended.
        self._is_stopping = threading.Event()
        self._is_active = threading.Event()
        # Held for the whole of one write. `close` and the writing thread both
        # end the body, and `close` does it whether or not the thread stopped in
        # time, so two of them can stand over the same socket: the body would
        # then carry a chunk after its own terminator, or a second terminator.
        self._body_lock = threading.Lock()

    @property
    def is_active(self) -> bool:
        """Whether the route is still taking audio, as PortAudio's `active`
        says a running stream is."""
        return self._is_active.is_set()

    # PortAudio's name for it, which the player reads of either stream.
    active = is_active

    def start(self) -> None:
        """Open the route and start writing, or raise `RuntimeError`."""
        try:
            self._connection = open_say(
                self._url, self._headers, self._sample_rate, self._timeout
            )
        except Exception as e:
            raise RuntimeError(
                f"Cannot reach the page's speaker at {self._url}{SPEAKER_PATH}: {e}"
            ) from e
        self._is_active.set()
        self._thread = threading.Thread(
            target=self._write, name="zrb-remote-speaker", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """End the body where it is and stop writing."""
        self._is_stopping.set()
        thread = self._thread
        if thread is not None:
            thread.join(_STOP_JOIN_SECONDS)

    def close(self) -> None:
        """Let the route go, whether or not its body ended cleanly."""
        self.stop()
        self._finish()

    def _write(self) -> None:
        """Write the player's blocks until stopped, at the rate they play.

        The clock is the device here: each block is due one block's worth of
        audio after the one before it, so a sentence is heard in the time it
        takes to say rather than as fast as the socket takes it — which is what
        keeps pausing, the play timeout and the underrun count honest.
        """
        due = time.monotonic()
        try:
            while not self._is_stopping.is_set():
                self._send(self._read(self._block_frames))
                due += self._block_seconds
                delay = due - time.monotonic()
                if delay > 0 and self._is_stopping.wait(delay):
                    break
        except (OSError, http.client.HTTPException, ValueError) as e:
            logger.warning(f"The page's speaker stopped: {e}")
        finally:
            self._finish()

    def _send(self, block: bytes) -> None:
        """Write *block* as one chunk of the body, or nothing once the body
        has already been ended."""
        with self._body_lock:
            connection = self._connection
            if connection is not None:
                connection.send(b"%x\r\n" % len(block) + block + b"\r\n")

    def _finish(self) -> None:
        """End the body, let the route go, and say when it refused the sentence.

        Whichever of the writing thread and `close` gets here first ends the
        body under the lock and takes the connection with it, so the other finds
        nothing to write and no second terminator. The reply is then read: a
        route that answers 4xx or 5xx is the whole reason nobody heard the
        sentence, and a closed socket alone never says so.
        """
        with self._body_lock:
            self._is_active.clear()
            connection, self._connection = self._connection, None
            if connection is None:
                return
            try:
                connection.send(_LAST_CHUNK)
            except (OSError, http.client.HTTPException):
                # The route went away before the body ended. Its answer, read
                # below, says more than a broken pipe does.
                pass
        try:
            self._report_refusal(connection)
        except (OSError, http.client.HTTPException) as e:
            logger.warning(f"Closing the page's speaker failed: {e}")
        finally:
            connection.close()

    def _report_refusal(self, connection: http.client.HTTPConnection) -> None:
        """Say a route that answered 4xx or 5xx, with what it answered with."""
        response = connection.getresponse()
        if response.status < http.HTTPStatus.BAD_REQUEST:
            return
        body = response.read(_REFUSAL_BODY_BYTES).decode("utf-8", "replace").strip()
        said = f"{response.status} {response.reason}"
        logger.warning(
            f"The page's speaker refused the sentence: {said}"
            + (f": {body}" if body else "")
        )


def open_say(
    url: str, headers: dict[str, str], sample_rate: int, timeout: float
) -> http.client.HTTPConnection:
    """The speaker route, open with its headers written; the body follows.

    The body is chunked, the one framing besides `Content-Length` the route
    takes, because a sentence's length is not known when it starts: the page
    hears the first block while the last is still being made. A base URL with
    no host in it is refused here, named, rather than at the socket.
    """
    parts = urllib.parse.urlsplit(f"{url}{SPEAKER_PATH}")
    if parts.hostname is None:
        raise RuntimeError(
            f"{url!r} names no host for the page's speaker; a base URL looks "
            "like http://127.0.0.1:7777."
        )
    connection = _connection_class(parts.scheme, url)(
        parts.hostname, parts.port, timeout=timeout
    )
    connection.putrequest("POST", parts.path)
    connection.putheader("Content-Type", "application/octet-stream")
    connection.putheader(SAMPLE_RATE_HEADER, str(sample_rate))
    connection.putheader("Transfer-Encoding", "chunked")
    for name, value in headers.items():
        connection.putheader(name, value)
    connection.endheaders()
    return connection


def _connection_class(scheme: str, url: str) -> "type[http.client.HTTPConnection]":
    """The connection *scheme* asks for, named when it asks for neither.

    `http.client.HTTPConnection` speaks cleartext on whatever port it is given,
    so a base URL that says `https` and is opened with it is posted in the
    clear, to port 80. The scheme picks the class, and each class picks its own
    default port when the URL names none — 443 for TLS, 80 for the other.
    """
    scheme = scheme.lower()
    if scheme == "https":
        return http.client.HTTPSConnection
    if scheme == "http":
        return http.client.HTTPConnection
    raise RuntimeError(
        f"{url!r} names a scheme the page's speaker does not speak "
        f"({scheme or 'none'!r}); a base URL looks like "
        "http://127.0.0.1:7777 or https://machine.tailnet.ts.net."
    )
