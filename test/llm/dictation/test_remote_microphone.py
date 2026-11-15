"""The page's microphone: one long GET, read into the cutter's blocks.

No phone and no face server reaches a test, so the server's part is played here
— a fake response hands int16 PCM over as a socket would — and a fake
sounddevice stands where the local device does. `open_microphone` is the seam
both come through, so these tests also hold the exclusivity the setting exists
for: with the page selected, this machine's microphone is never opened, and
without it, nothing asks the network anything.
"""

import asyncio
import email.message
import time
from unittest.mock import MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.dictation import remote_microphone
from zrb.llm.dictation.microphone import SAMPLE_RATE, close_microphone, open_microphone
from zrb.llm.dictation.remote_microphone import RemoteMicrophone, open_audio_in

np = pytest.importorskip("numpy")

REMOTE_URL = "http://127.0.0.1:7777"


class FakeResponse:
    """The `HTTPResponse` one long GET comes back as: its body read a piece at
    a time, the way a socket hands one over."""

    def __init__(self, body, headers=None, error=None):
        self.headers = email.message.Message()
        for name, value in {
            "X-Sample-Rate": SAMPLE_RATE,
            "X-Sample-Width": 2,
            "X-Channels": 1,
            **(headers or {}),
        }.items():
            self.headers[name] = str(value)
        self.is_closed = False
        self._pieces = [body] if isinstance(body, bytes) else list(body)
        self._error = error

    def read1(self, size):
        if self._error is not None:
            raise self._error
        if not self._pieces:
            return b""
        piece = self._pieces[0]
        if len(piece) <= size:
            self._pieces.pop(0)
            return piece
        self._pieces[0] = piece[size:]
        return piece[:size]

    def close(self):
        self.is_closed = True


class FakeStream:
    """The `sounddevice.InputStream` the local path opens."""

    active = True

    def __init__(self):
        self.is_started = False
        self.is_closed = False

    def start(self):
        self.is_started = True

    def close(self):
        self.is_closed = True


def _pcm(*values):
    return np.array(values, dtype=np.int16).tobytes()


def _wait_for(condition, timeout=2.0):
    """Wait for *condition*, which the reading thread makes true."""
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.005)


def _remote_microphone(blocksize=4):
    """A `RemoteMicrophone` whose blocks the caller collects."""
    blocks = []
    microphone = RemoteMicrophone(
        np,
        lambda indata, frames, time_info, status: blocks.append(indata),
        url=REMOTE_URL,
        headers={},
        samplerate=SAMPLE_RATE,
        blocksize=blocksize,
        timeout=5,
    )
    return microphone, blocks


def _serve(monkeypatch, response):
    asked = {}

    def open_route(url, headers, timeout):
        asked["url"], asked["headers"] = url, headers
        return response

    monkeypatch.setattr(remote_microphone, "open_audio_in", open_route)
    return asked


def test_the_route_is_a_get_carrying_the_servers_headers(monkeypatch):
    """One long GET to the route, with whatever the server's token makes: no
    length, no framing, and the body read as it arrives."""
    asked = {}
    response = FakeResponse(b"")

    def urlopen(request, timeout):
        asked["request"], asked["timeout"] = request, timeout
        return response

    monkeypatch.setattr(remote_microphone.urllib.request, "urlopen", urlopen)

    assert open_audio_in(REMOTE_URL, {"Authorization": "Bearer shared"}, 5) is response
    assert asked["request"].get_method() == "GET"
    assert asked["request"].full_url == f"{REMOTE_URL}/audio/in"
    assert asked["request"].get_header("Authorization") == "Bearer shared"
    assert asked["timeout"] == 5


def test_the_callback_gets_blocks_of_the_shape_the_cutter_takes(monkeypatch):
    _serve(monkeypatch, FakeResponse(_pcm(*([16384] * 8))))
    microphone, blocks = _remote_microphone(blocksize=4)

    microphone.start()
    _wait_for(lambda: len(blocks) >= 2)
    microphone.close()

    assert [block.shape for block in blocks[:2]] == [(4, 1), (4, 1)]
    assert blocks[0][0][0] == pytest.approx(0.5)


def test_the_request_goes_to_the_microphone_route_with_its_headers(monkeypatch):
    asked = _serve(monkeypatch, FakeResponse(_pcm(0)))
    microphone, _ = _remote_microphone()

    microphone.start()
    microphone.close()

    assert asked["url"] == REMOTE_URL
    assert asked["headers"] == {}


def test_a_sample_split_by_the_socket_is_kept_whole(monkeypatch):
    """Nothing frames the body at a sample boundary, so half a sample has to
    wait for the read that completes it rather than be dropped."""
    sample = _pcm(16384)
    _serve(monkeypatch, FakeResponse([sample[:1], sample[1:]]))
    microphone, blocks = _remote_microphone(blocksize=1)

    microphone.start()
    _wait_for(lambda: blocks)
    microphone.close()

    assert len(blocks) == 1
    assert blocks[0][0][0] == pytest.approx(0.5)


def test_a_route_that_ends_leaves_it_inactive(monkeypatch):
    """Reading to EOF is the page or the server going away, which `listen`
    reopens from — the same way it reopens a stream PortAudio stopped."""
    _serve(monkeypatch, FakeResponse(_pcm(*([0] * 4))))
    microphone, blocks = _remote_microphone(blocksize=4)

    microphone.start()
    _wait_for(lambda: not microphone.active)

    assert blocks
    assert not microphone.active


def test_a_read_that_fails_ends_the_route_and_says_so_once(monkeypatch, caplog):
    _serve(monkeypatch, FakeResponse(b"", error=OSError("the socket went away")))
    microphone, _ = _remote_microphone()

    microphone.start()
    _wait_for(lambda: not microphone.active)

    assert not microphone.active
    assert "The page's microphone stopped" in caplog.text


def test_a_route_of_another_format_is_refused_before_a_block(monkeypatch):
    _serve(monkeypatch, FakeResponse(_pcm(0), headers={"X-Sample-Rate": "44100"}))
    microphone, blocks = _remote_microphone()

    with pytest.raises(RuntimeError) as refusal:
        microphone.start()

    assert "44100" in str(refusal.value)
    assert blocks == []


def test_closing_lets_the_route_go(monkeypatch):
    response = FakeResponse(_pcm(*([0] * 64)))
    _serve(monkeypatch, response)
    microphone, _ = _remote_microphone()

    microphone.start()
    microphone.close()

    assert response.is_closed
    assert not microphone.active


def test_open_microphone_takes_the_page_and_never_this_machine(monkeypatch):
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", REMOTE_URL)
    asked = _serve(monkeypatch, FakeResponse(_pcm(*([0] * 8))))
    sd = MagicMock()
    blocks = []

    async def run():
        stream = await open_microphone(
            sd,
            lambda indata, frames, time_info, status: blocks.append(indata),
            blocksize=4,
        )
        try:
            _wait_for(lambda: blocks)
            return stream
        finally:
            await close_microphone(stream.close, "the page's microphone")

    stream = asyncio.run(run())

    assert isinstance(stream, RemoteMicrophone)
    assert asked["url"] == REMOTE_URL
    sd.InputStream.assert_not_called()


def test_a_server_that_cannot_be_reached_says_what_to_do(monkeypatch):
    """No local microphone stands in: a room nobody is speaking into, handed to
    the transcriber, is the failure this prevents."""
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", REMOTE_URL)

    def refuse(url, headers, timeout):
        raise OSError("Connection refused")

    monkeypatch.setattr(remote_microphone, "open_audio_in", refuse)
    sd = MagicMock()

    with pytest.raises(RuntimeError) as refusal:
        asyncio.run(open_microphone(sd, lambda *args: None, blocksize=4))

    message = str(refusal.value)
    assert REMOTE_URL in message
    assert "LLM_VOICE_REMOTE_URL" in message
    sd.InputStream.assert_not_called()


def test_without_the_setting_the_local_microphone_opens_as_it_always_did(monkeypatch):
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", raising=False)
    asked = _serve(monkeypatch, FakeResponse(b""))
    captured = {}

    def make_stream(**options):
        captured.update(options)
        return FakeStream()

    sd = MagicMock()
    sd.InputStream.side_effect = make_stream

    stream = asyncio.run(open_microphone(sd, lambda *args: None, blocksize=160))

    assert isinstance(stream, FakeStream)
    assert captured["samplerate"] == SAMPLE_RATE
    assert captured["channels"] == 1
    assert asked == {}
