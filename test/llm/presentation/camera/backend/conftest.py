"""A face server's camera routes, played in process: one page, two cameras.

The routes are real ones — a `ThreadingHTTPServer` on a loopback port nobody
else has — because the thing being tested is the conversation with that server:
the URL it builds, the status it turns into a sentence, the headers that travel.
A mocked `urlopen` would agree with whatever this side believed.

The other fixture here is `clean_env`, which the ffmpeg-backend tests ask for: it
strips `WSL_DISTRO_NAME` and `WSLENV`, because those two decide which camera path
a backend takes, and the shell that started pytest may have either of them set.
"""

from __future__ import annotations

import http.server
import json
import threading
import time

import pytest

# The first two bytes are what makes it a JPEG to `RemoteCameraBackend`.
JPEG = b"\xff\xd8\xff\xe0" + b"a photo" + b"\xff\xd9"

# How long a body may keep trickling before the fake page gives up on it: long
# enough for a backend's deadline to fire, short enough not to outlive the test.
TRICKLE_SECONDS = 3.0


class FakePage:
    """What the page answers with, and every request it was asked."""

    def __init__(self) -> None:
        self.url = ""
        self.devices: list[str] = ["phone-back", "phone-front"]
        self.jpeg = JPEG
        self.content_type = "image/jpeg"
        self.status = 200
        self.failure = "no page is open"
        self.delay_seconds = 0.0
        # A body that stops short of the length it promised, and one that arrives
        # a byte at a time and never finishes. Neither is a photo; only the first
        # is an exception the client is handed rather than a read that returns.
        self.truncate_at: int | None = None
        self.trickle: tuple[int, float] | None = None
        # (path, Authorization header or None), in the order asked.
        self.requests: list[tuple[str, str | None]] = []

    def note(self, path: str, authorization: str | None) -> None:
        self.requests.append((path, authorization))

    @property
    def frame_requests(self) -> list[str]:
        """The shots asked for, without the listings a test did as its setup."""
        return [
            path
            for path, _ in self.requests
            if path.startswith("/frame?") or path == "/frame"
        ]

    def answer_devices(self, handler: http.server.BaseHTTPRequestHandler) -> None:
        self._wait()
        if self.status != 200:
            handler.send_error(self.status, self.failure)
            return
        body = json.dumps({"devices": self.devices}).encode()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def answer_frame(self, handler: http.server.BaseHTTPRequestHandler) -> None:
        self._wait()
        if self.status != 200:
            handler.send_error(self.status, self.failure)
            return
        handler.send_response(200)
        handler.send_header("Content-Type", self.content_type)
        handler.send_header("Content-Length", str(len(self.jpeg)))
        handler.end_headers()
        if self.trickle is not None:
            return self._drip(handler)
        sent = len(self.jpeg) if self.truncate_at is None else self.truncate_at
        handler.wfile.write(self.jpeg[:sent])
        # The handler returns here and the connection closes with the length
        # promise unkept, which is what a proxy that gives up mid-body does.

    def _drip(self, handler: http.server.BaseHTTPRequestHandler) -> None:
        """The body a little at a time, never all of it.

        Each socket read returns something, so a client that bounds only its own
        reads never times out: the request stays open until this loop ends.
        """
        trickle = self.trickle
        if trickle is None:
            return
        size, pause = trickle
        deadline = time.monotonic() + TRICKLE_SECONDS
        try:
            while time.monotonic() < deadline:
                handler.wfile.write(self.jpeg[:size])
                handler.wfile.flush()
                time.sleep(pause)
        except OSError:
            pass  # the client gave up on it, which is the case being tested

    def _wait(self) -> None:
        if self.delay_seconds:
            time.sleep(self.delay_seconds)


class QuietServer(http.server.ThreadingHTTPServer):
    """A page whose client hung up: that is the test, not a server fault."""

    def handle_error(self, request, client_address):
        pass


@pytest.fixture
def face_page():
    page = FakePage()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            page.note(self.path, self.headers.get("Authorization"))
            if self.path.startswith("/frame/devices"):
                return page.answer_devices(self)
            return page.answer_frame(self)

        def log_message(self, format, *args):
            pass

    server = QuietServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    page.url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield page
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


@pytest.fixture
def clean_env(monkeypatch):
    "Strip every camera-relevant env var before each test."
    for var in ("WSL_DISTRO_NAME", "WSLENV"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch
