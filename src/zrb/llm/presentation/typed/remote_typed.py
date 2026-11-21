"""Typed lines from the page, read off the face server as whole messages.

With `LLM_VOICE_REMOTE_URL` set, the page that holds the microphone also holds a
text box: a phone across the room has a keyboard of its own, and a line typed
there has to reach the chat the way a spoken one does. `GET /text/in` is one long
response of newline-framed UTF-8 lines, read here on a thread of its own and
handed on one message at a time, so nothing else knows typing is not happening
at this keyboard.

A route that ends -- the page reloaded, the server restarted -- is reconnected
rather than taken for the end of typing, because a session outlives both and a
box that stopped working after one reload would have to be reopened by hand. A
server that has no such route at all (an older page, or one with no box on it)
is not retried: it says so once and ends, since asking again changes nothing.
"""

from __future__ import annotations

import asyncio
import http.client
import logging
import socket
import threading
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Iterator

from zrb.llm.contracts.util.face_server import TYPED_PATH

logger = logging.getLogger(__name__)

# What the reading thread hands the waiting generator when it has given up: a
# line is always text, so a sentinel cannot be mistaken for one.
_DONE = object()

# How long to wait before asking again after a route ended or failed. Long
# enough not to hammer a server that is restarting, short enough that a line
# typed across the wait is not the one that lands in the gap.
RECONNECT_SECONDS = 1.0
# How long a read may wait for a line. The server writes a blank line every
# fifteen seconds whether anything is typed or not, so a silence longer than
# twice that is a route nobody holds open any more.
READ_TIMEOUT_SECONDS = 35.0
# How long closing may take: the thread is already ending, and a page that went
# away must not hold a session's teardown.
_CLOSE_JOIN_SECONDS = 1.0


class RemoteTyped:
    """The page's text box: GET /text/in, handed on one line at a time.

    *url* is the face server and *headers* travel with the request. *loop* is the
    loop the lines are handed back to, because the route is read on a thread of
    its own -- a long response cannot be awaited without holding the loop open
    for a line that may not come for minutes.
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str],
        loop: asyncio.AbstractEventLoop,
        timeout: float = READ_TIMEOUT_SECONDS,
    ) -> None:
        self._url = url
        self._headers = headers
        self._loop = loop
        self._timeout = timeout
        self._lines: "asyncio.Queue[object]" = asyncio.Queue()
        self._stop = threading.Event()
        # The route being read, so a generator that is finished can break its read instead of
        # waiting for a line that may be a keepalive away.
        self._active: http.client.HTTPResponse | None = None
        self._active_lock = threading.Lock()
        # Whether the last thing said about this route has been said: a server
        # that is down is one message, not one a second until it comes back.
        self._said = False

    async def lines(self) -> AsyncIterator[str]:
        """Every line typed on the page, in order, while this is being read."""
        thread = threading.Thread(
            target=self._read, name="zrb-remote-typed", daemon=True
        )
        thread.start()
        try:
            while True:
                item = await self._lines.get()
                if item is _DONE:
                    return
                yield str(item)
        finally:
            # The session is over, or whoever read this has closed it: the route is let go rather
            # than left writing into a queue nobody reads. The read in flight is broken at once --
            # a close would wait for it -- so neither the thread nor the connection outlives the
            # generator that asked for them.
            self._stop.set()
            self._release()
            thread.join(_CLOSE_JOIN_SECONDS)

    def _read(self) -> None:
        """Read the route, reconnecting for as long as the session lasts."""
        while not self._stop.is_set():
            try:
                response = open_typed_in(self._url, self._headers, self._timeout)
            except urllib.error.HTTPError as e:  # first: an HTTPError is an OSError too
                if e.code == 404:
                    self._give_up("this page has no text box")
                    return
                self._retry(f"cannot reach the page's text box: {e}")
                continue
            except (OSError, http.client.HTTPException, ValueError) as e:
                # A server that is not up yet, a URL that cannot be used, a body cut off
                # mid-line: all of them are worth asking again, and none of them is the end
                # of a session that outlives the server it reads.
                self._retry(f"cannot reach the page's text box: {e}")
                continue
            self._said = False
            self._hold(response)
            try:
                for line in _typed_lines(response, self._stop):
                    self._hand_over(line)
            except (OSError, http.client.HTTPException) as e:
                logger.warning(f"The page's text box stopped: {e}")
            finally:
                self._forget(response)
                response.close()
            self._stop.wait(RECONNECT_SECONDS)

    def _hold(self, response: http.client.HTTPResponse) -> None:
        """Remember the route being read, so it can be broken rather than waited on."""
        with self._active_lock:
            self._active = response

    def _forget(self, response: http.client.HTTPResponse) -> None:
        """This route is over: it is nobody's to break any more."""
        with self._active_lock:
            if self._active is response:
                self._active = None

    def _release(self) -> None:
        """Break the read that is in flight, if any: the route is being let go now.

        Closing the response would wait for that read -- the file object's lock is held by it --
        which is the wait a teardown must not have. Shutting the socket down makes the read return
        at once; the thread then closes the response on the path it already has.
        """
        with self._active_lock:
            response = self._active
        if response is not None:
            _abort(response)

    def _hand_over(self, line: str) -> None:
        """Give *line* to the generator, on the loop that is waiting for it."""
        try:
            self._loop.call_soon_threadsafe(self._lines.put_nowait, line)
        except RuntimeError:  # the loop is closing: nothing left to hand it to
            self._stop.set()

    def _retry(self, reason: str) -> None:
        """Say *reason* once, then wait to be asked again."""
        if not self._said:
            logger.info(f"{reason} at {self._url}{TYPED_PATH}")
            self._said = True
        self._stop.wait(RECONNECT_SECONDS)

    def _give_up(self, reason: str) -> None:
        """Say *reason* and end: asking again would get the same answer."""
        logger.info(f"{reason} at {self._url}{TYPED_PATH}")
        try:
            self._loop.call_soon_threadsafe(self._lines.put_nowait, _DONE)
        except RuntimeError:  # the loop is closing, which ends it just as well
            pass


def _abort(response: http.client.HTTPResponse) -> None:
    """Make a read that is blocked in ``readline()`` return.

    ``response.close()`` is not the way: the file object's lock is held by the read, so closing
    waits for it -- exactly the wait a teardown must not have. The socket underneath is what the
    read is actually waiting on, and shutting it down ends that wait at once. A response whose
    socket cannot be reached is left to notice its next line, which the server writes every fifteen
    seconds.
    """
    raw = getattr(getattr(response, "fp", None), "raw", None)
    sock = getattr(raw, "_sock", None)
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:  # already closed, which is what was wanted
        pass


def _typed_lines(
    response: http.client.HTTPResponse, stop: threading.Event
) -> Iterator[str]:
    """The lines of *response*, without the blank ones it writes to stay alive.

    A blank line is also where a stop is noticed, as a backstop: a read nobody has broken ends at the
    next keepalive, and the server writes one every fifteen seconds.
    """
    while not stop.is_set():
        raw = response.readline()
        if not raw:
            return
        if not raw.endswith(b"\n"):
            # The route ended mid-line, so these are the bytes of a line that never finished
            # arriving rather than a message. The server gives an unsent line back for the
            # reconnect, which reads it whole: handing the fragment on is one sentence arriving
            # twice, the first time cut short.
            return
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if line:
            yield line


class RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Refuse a redirect: the request carries the face server's token, and urllib's handler would
    take that header to whatever host the answer named."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url, code, f"refused a redirect to {newurl}", headers, fp
        )


_opener = urllib.request.build_opener(RefuseRedirects)


def open_typed_in(
    url: str,
    headers: dict[str, str],
    timeout: float,
    opener: urllib.request.OpenerDirector | None = None,
) -> http.client.HTTPResponse:
    """The text box route, open: one long response of newline-framed UTF-8.

    *opener* is where a test stands in for the connection; a session leaves it out.
    """
    request = urllib.request.Request(f"{url}{TYPED_PATH}", headers=headers)
    return (opener or _opener).open(request, timeout=timeout)
