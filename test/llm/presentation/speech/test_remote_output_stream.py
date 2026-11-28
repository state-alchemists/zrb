"""The page's speaker: the player's blocks, posted as they come due.

The socket is faked at `http.client`, so what is under test is ours — the
request the stream opens, the chunked body it writes, the pace it writes at,
and the end it gives a body that is stopped — and above it, `PcmUtterance`
playing a sentence into the page rather than a device. No device is opened on
that path at all, which is what the fake sounddevice in the other half of this
file is there to prove: with the setting unset, the device opens as it always
did, and nothing is posted.
"""

import threading
import time
import types

import pytest

from zrb.config.config import CFG
from zrb.llm.presentation.speech import pcm_player, remote_output_stream
from zrb.llm.presentation.speech.backend.audio import SpeechAudio
from zrb.llm.presentation.speech.pcm_player import PcmUtterance
from zrb.llm.presentation.speech.remote_output_stream import (
    RemoteOutputStream,
    open_say,
)

np = pytest.importorskip("numpy")

REMOTE_URL = "http://127.0.0.1:7777"
RATE = 16000


class FakeResponse:
    """What the route answers once the body has ended."""

    def __init__(self, status, reason, body=b""):
        self.status = status
        self.reason = reason
        self._body = body

    def read(self, size=-1):
        return self._body


class FakeConnection:
    """The `http.client.HTTPConnection` the stream writes to, recording what
    the server would have read."""

    instances: "list[FakeConnection]" = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout = host, port, timeout
        self.request = None
        self.headers = []
        self.written = b""
        self.is_closed = False
        self.is_failing = False
        # What the server said when the body ended: nothing, unless a test
        # makes it refuse one.
        self.response = FakeResponse(204, "No Content")
        FakeConnection.instances.append(self)

    def putrequest(self, method, path):
        self.request = (method, path)

    def putheader(self, name, value):
        self.headers.append((name, value))

    def endheaders(self):
        self.is_ended = True

    def send(self, data):
        if self.is_failing:
            raise OSError("the socket went away")
        self.written += data

    def close(self):
        self.is_closed = True

    def getresponse(self):
        return self.response

    def refuse(self, status, reason, body=""):
        """Answer the way a route refuses a sentence it will not play."""
        self.response = FakeResponse(status, reason, body.encode())

    def posted_pcm(self):
        """The body with its chunk framing taken off."""
        raw, body = self.written, b""
        while raw:
            size_line, rest = raw.split(b"\r\n", 1)
            size = int(size_line, 16)
            body += rest[:size]
            raw = rest[size + 2 :]
            if size == 0:
                break
        return body

    def has_terminator(self):
        return self.written.endswith(b"0\r\n\r\n")


class FakeOutputStream:
    """The device `sounddevice.OutputStream` opens, calling back on a thread of
    its own as PortAudio does."""

    instances: "list[FakeOutputStream]" = []

    def __init__(self, **options):
        self.options = options
        self.rate = options["samplerate"]
        self.blocksize = options["blocksize"]
        self.is_closed = False
        self._is_running = False
        FakeOutputStream.instances.append(self)

    @property
    def active(self):
        return self._is_running

    def start(self):
        self._is_running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._is_running = False

    def close(self):
        self._is_running = False
        self.is_closed = True

    def _run(self):
        while self._is_running:
            out = np.zeros((self.blocksize, 1), np.int16)
            self.options["callback"](out, self.blocksize, None, None)
            time.sleep(0.001)


@pytest.fixture
def connection(monkeypatch):
    """The socket the stream opens, and the record of it."""
    FakeConnection.instances = []
    monkeypatch.setattr(
        remote_output_stream.http.client, "HTTPConnection", FakeConnection
    )
    return FakeConnection


def _wait_for(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.005)


def _posted(connection, at_least: int) -> bool:
    """Whether the first connection has been sent *at_least* bytes of body."""
    return bool(connection.instances) and (
        len(connection.instances[0].posted_pcm()) >= at_least
    )


def _stream(blocksize=160, blocks=None):
    """A `RemoteOutputStream` over *blocks*: the next one, then silence."""
    pending = list(blocks or [])
    return RemoteOutputStream(
        read=lambda frames: pending.pop(0) if pending else b"\x00\x00" * frames,
        sample_rate=RATE,
        block_frames=blocksize,
        url=REMOTE_URL,
        headers={"Authorization": "Bearer shared"},
        timeout=5,
    )


def test_the_route_is_a_chunked_post_naming_the_rate(connection):
    stream = _stream(blocksize=160)

    stream.start()
    stream.stop()

    sent = connection.instances[0]
    assert sent.request == ("POST", "/say")
    assert (sent.host, sent.port) == ("127.0.0.1", 7777)
    assert ("X-Sample-Rate", str(RATE)) in sent.headers
    assert ("Transfer-Encoding", "chunked") in sent.headers
    assert ("Authorization", "Bearer shared") in sent.headers


def test_blocks_are_posted_in_the_order_they_play(connection):
    first = np.array([1] * 160, np.int16).tobytes()
    second = np.array([2] * 160, np.int16).tobytes()
    stream = _stream(blocks=[first, second])

    stream.start()
    _wait_for(lambda: connection.instances and _posted(connection, 640))
    stream.stop()

    assert connection.instances[0].posted_pcm()[:640] == first + second


def test_blocks_are_posted_at_the_rate_they_play(connection):
    """Unpaced, a sentence would be posted as fast as the socket takes it; the
    clock is what keeps a pause, the play timeout and the underrun count true."""
    stream = _stream(blocksize=160)  # 10 ms a block

    stream.start()
    time.sleep(0.2)
    stream.stop()

    posted = connection.instances[0].posted_pcm()
    assert len(posted) // 320 < 60  # a 10 ms block, over 0.2 s: about 20


def test_stopping_ends_the_body_and_lets_the_route_go(connection):
    stream = _stream()

    stream.start()
    stream.stop()
    stream.close()

    sent = connection.instances[0]
    assert sent.has_terminator()
    assert sent.is_closed
    assert not stream.active


def test_a_route_that_fails_stops_playing(connection):
    stream = _stream(blocksize=160)

    stream.start()
    connection.instances[0].is_failing = True
    _wait_for(lambda: not stream.active)
    stream.close()

    assert not stream.active


def test_a_url_with_no_host_says_which_url(connection):
    with pytest.raises(RuntimeError) as refusal:
        open_say("/only-a-path", {}, RATE, 1)

    assert "names no host" in str(refusal.value)


def test_a_server_that_cannot_be_reached_says_where(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("Connection refused")

    monkeypatch.setattr(remote_output_stream.http.client, "HTTPConnection", refuse)

    with pytest.raises(RuntimeError) as refusal:
        _stream().start()

    assert REMOTE_URL in str(refusal.value)


def test_speech_goes_to_the_page_and_no_device_is_opened(monkeypatch, connection):
    """The whole point of the setting: with it, this machine opens nothing, so
    PortAudio is not imported at all on the way."""
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_FACE_SERVER_URL", REMOTE_URL)

    def no_portaudio():
        raise AssertionError("the page's speaker must not start PortAudio")

    monkeypatch.setattr(pcm_player, "_import_audio", no_portaudio)
    pcm = np.array([7] * 480, np.int16).tobytes()
    utterance = PcmUtterance(SpeechAudio(RATE, [pcm]), block_frames=480)

    utterance.play(10)

    assert connection.instances
    assert connection.instances[0].posted_pcm()[: len(pcm)] == pcm
    assert FakeOutputStream.instances == []


def test_without_the_setting_the_device_opens_as_it_always_did(monkeypatch, connection):
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_FACE_SERVER_URL", raising=False)
    FakeOutputStream.instances = []
    fake_sd = types.SimpleNamespace(OutputStream=FakeOutputStream)
    monkeypatch.setattr(pcm_player, "_import_audio", lambda: (np, fake_sd))
    monkeypatch.setattr(pcm_player, "_start_portaudio_again", lambda sd: None)
    monkeypatch.setattr(pcm_player, "_follow_the_default_output", lambda sd: None)
    pcm = np.array([7] * 480, np.int16).tobytes()
    utterance = PcmUtterance(SpeechAudio(RATE, [pcm]), block_frames=240)

    utterance.play(10)

    assert FakeOutputStream.instances
    assert FakeOutputStream.instances[0].close
    assert connection.instances == []


def test_the_page_s_stream_is_counted_while_it_is_open(monkeypatch, connection):
    """Its opening is counted, because every path that retires a stream says it
    has closed. An uncounted one leaves the count negative, and then
    `wait_for_streams_to_close` waits for a zero it has already passed, so a
    process ending after a sentence was said on the page never exits."""
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_FACE_SERVER_URL", REMOTE_URL)
    assert not pcm_player.has_open_streams()
    pcm = np.zeros(RATE // 2, np.int16).tobytes()  # half a second, block by block
    utterance = PcmUtterance(SpeechAudio(RATE, [pcm]), block_frames=160)
    playing = threading.Thread(target=utterance.play, args=(10,), daemon=True)

    playing.start()
    try:
        _wait_for(pcm_player.has_open_streams)
        assert pcm_player.has_open_streams()
    finally:
        playing.join(10)

    assert not pcm_player.has_open_streams()


def test_an_https_url_is_posted_over_tls(monkeypatch):
    """The cleartext class speaks on whatever port it is given, so an `https`
    base URL opened with it goes out in the clear, to port eighty. The scheme
    picks the class, and the class picks 443 when the URL names no port."""
    FakeConnection.instances = []
    monkeypatch.setattr(
        remote_output_stream.http.client, "HTTPSConnection", FakeConnection
    )
    monkeypatch.setattr(
        remote_output_stream.http.client, "HTTPConnection", _must_not_be_used
    )

    connection = open_say("https://machine.tail4204a7.ts.net", {}, RATE, 1)

    assert connection is FakeConnection.instances[0]
    assert (connection.host, connection.port) == ("machine.tail4204a7.ts.net", None)


def _must_not_be_used(*args, **kwargs):
    raise AssertionError("an https URL must not be opened in cleartext")


def test_a_scheme_the_speaker_cannot_speak_is_named():
    with pytest.raises(RuntimeError) as refusal:
        open_say("ftp://127.0.0.1:7777", {}, RATE, 1)

    assert "ftp" in str(refusal.value)


def test_a_refused_sentence_is_said(connection, caplog):
    """A route answers 415 for a rate it cannot play, and the sentence is then
    never heard. The reply read once the body has ended is the only place that
    says why, so a closed socket is not enough of an answer."""
    stream = _stream(blocksize=160)

    stream.start()
    connection.instances[0].refuse(
        415, "Unsupported Media Type", "rate 16000 is not one this page plays"
    )
    stream.close()

    assert "415" in caplog.text
    assert "rate 16000 is not one this page plays" in caplog.text


def test_closing_while_the_writer_runs_ends_the_body_once(connection, monkeypatch):
    """`close` ends the body whether or not the writing thread stopped in time,
    and that thread ends it too from its own finally: two writers on one
    chunked body would put a chunk after the terminator, or a second one."""
    monkeypatch.setattr(remote_output_stream, "_STOP_JOIN_SECONDS", 0)
    stream = _stream(blocksize=160)

    stream.start()
    stream.close()

    sent = connection.instances[0]
    assert sent.written.count(b"0\r\n\r\n") == 1
    assert sent.has_terminator()
