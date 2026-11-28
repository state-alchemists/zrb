"""The page's text box: one long GET, read as whole messages.

No phone and no face server reaches a test, so the server's part is played here
-- a fake response hands lines over the way a socket would, blank ones included
-- and `open_typed_in` is the one seam they come through.
"""

import asyncio
import contextlib
import threading
import time
import types
import urllib.error
import urllib.request

import pytest

from zrb.config.config import CFG
from zrb.llm.contracts.shared.input_source import WEB_INPUT
from zrb.llm.presentation.typed import feature, remote_typed
from zrb.llm.presentation.typed.feature import enable_typed_input
from zrb.llm.presentation.typed.remote_typed import RemoteTyped, open_typed_in

REMOTE_URL = "http://127.0.0.1:7777"


class FakeResponse:
    """An `HTTPResponse` whose lines are handed over as they were written."""

    def __init__(self, lines, error=None):
        self._lines = [
            line if isinstance(line, bytes) else line.encode() for line in lines
        ]
        self._error = error
        self.is_closed = False

    def readline(self):
        if self._error is not None:
            raise self._error
        return self._lines.pop(0) if self._lines else b""

    def close(self):
        self.is_closed = True


class EndlessResponse:
    """A route that stays open and keeps writing the keepalive, as a quiet one does."""

    def __init__(self, first):
        self._first = first.encode()
        self.reads = 0
        self.is_closed = False

    def readline(self):
        if self._first:
            line, self._first = self._first, b""
            return line
        self.reads += 1
        time.sleep(
            0.005
        )  # the server writes every fifteen seconds; the shape is the same
        return b"\n"

    def close(self):
        self.is_closed = True


class BlockingResponse:
    """A route that has gone quiet: ``readline()`` waits for a line that does not come."""

    def __init__(self):
        self.reading = threading.Event()
        self.broken = threading.Event()
        self.is_closed = False
        self.fp = types.SimpleNamespace(raw=types.SimpleNamespace(_sock=self))

    def shutdown(self, how):  # what the socket underneath the response does
        self.broken.set()

    def readline(self):
        self.reading.set()
        self.broken.wait(10)
        raise OSError("the route was let go")

    def close(self):
        self.is_closed = True


def _no_text_box():
    """What a page with no box on it answers: the one code the reader does not retry."""
    return urllib.error.HTTPError(f"{REMOTE_URL}/text/in", 404, "Not Found", None, None)


def _serve_in_order(monkeypatch, *responses):
    """Hand `open_typed_in` each response in turn, then report no text box."""
    remaining = list(responses)
    asked = []

    def open_route(url, headers, timeout):
        asked.append((url, headers, timeout))
        if not remaining:
            raise _no_text_box()
        item = remaining.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(remote_typed, "open_typed_in", open_route)
    monkeypatch.setattr(remote_typed, "RECONNECT_SECONDS", 0.01)
    return asked


def _reader():
    return RemoteTyped(REMOTE_URL, {}, asyncio.get_running_loop(), timeout=5)


async def _first_lines(count, reader=None, timeout=3.0):
    """The first *count* lines the reader hands on, then let it go."""

    async def take():
        lines = []
        async for line in (reader or _reader()).lines():
            lines.append(line)
            if len(lines) >= count:
                break
        return lines

    return await asyncio.wait_for(take(), timeout)


def test_a_line_typed_on_the_page_arrives_whole(monkeypatch):
    _serve_in_order(monkeypatch, FakeResponse(["hello there\n"]))

    assert asyncio.run(_first_lines(1)) == ["hello there"]


def test_the_blank_line_the_server_writes_is_not_a_message(monkeypatch):
    """The route writes a blank line to stay alive; a reader that counted it
    would send the chat an empty turn every fifteen seconds."""
    _serve_in_order(monkeypatch, FakeResponse(["\n", "after the quiet\n", "\n"]))

    assert asyncio.run(_first_lines(1)) == ["after the quiet"]


def test_a_line_cut_off_midway_is_not_a_message(monkeypatch):
    """The server terminates every line it writes, so an unterminated one is a line that never
    finished arriving -- and the server gives that line back for the reconnect. Handing the
    fragment on is one sentence arriving twice, the first time cut short."""
    _serve_in_order(monkeypatch, FakeResponse(["only the fir"]))

    async def everything():
        return [line async for line in _reader().lines()]

    assert asyncio.run(asyncio.wait_for(everything(), 3)) == []


def test_a_line_cut_off_is_given_back_and_arrives_once(monkeypatch):
    """A write that fails partway leaves the line with the server, which puts it back: the
    reconnect reads it whole, so the message arrives once rather than as a prefix and a copy.
    """
    _serve_in_order(
        monkeypatch, FakeResponse(["hello th"]), FakeResponse(["hello there\n"])
    )

    assert asyncio.run(_first_lines(1)) == ["hello there"]


def test_a_page_with_no_text_box_ends_the_reader(monkeypatch):
    """An older page has no such route, and asking again would say so again."""
    asked = _serve_in_order(monkeypatch)

    async def everything():
        return [line async for line in _reader().lines()]

    assert asyncio.run(asyncio.wait_for(everything(), 3)) == []
    assert len(asked) == 1, "the reader keeps asking a page that has no box"


def test_a_route_that_ends_is_reconnected(monkeypatch):
    """A page reloads and a server restarts; the session outlives both, so the
    next line typed after either still arrives."""
    _serve_in_order(
        monkeypatch,
        FakeResponse(["before the reload\n"]),
        FakeResponse(["after the reload\n"]),
    )

    assert asyncio.run(_first_lines(2)) == ["before the reload", "after the reload"]


def test_a_read_that_fails_is_retried_and_does_not_end_typing(monkeypatch, caplog):
    """A socket that goes away is not the end of a session: the page is opened
    again, and the line typed after it is the one that matters."""
    _serve_in_order(
        monkeypatch,
        FakeResponse([], error=OSError("the socket went away")),
        FakeResponse(["after the socket came back\n"]),
    )

    assert asyncio.run(_first_lines(1)) == ["after the socket came back"]
    assert "The page's text box stopped" in caplog.text


def test_the_route_is_a_get_carrying_the_servers_token(monkeypatch):
    asked = {}

    class Opener:
        def open(self, request, timeout):
            asked["request"], asked["timeout"] = request, timeout
            return FakeResponse([])

    response = open_typed_in(
        REMOTE_URL, {"Authorization": "Bearer shared"}, 5, opener=Opener()
    )

    assert isinstance(response, FakeResponse)
    assert asked["request"].get_method() == "GET"
    assert asked["request"].full_url == f"{REMOTE_URL}/text/in"
    assert asked["request"].get_header("Authorization") == "Bearer shared"
    assert asked["timeout"] == 5


def test_a_redirect_is_refused_rather_than_followed():
    """The request carries the face server's token, and urllib's redirect handler takes every header
    with it: an answer naming another host would hand that token over."""
    request = urllib.request.Request(f"{REMOTE_URL}{remote_typed.TYPED_PATH}")

    with pytest.raises(urllib.error.HTTPError):
        remote_typed.RefuseRedirects().redirect_request(
            request, None, 302, "Found", {}, "http://elsewhere.test/text/in"
        )


def test_a_reader_that_is_let_go_closes_its_route(monkeypatch):
    """A session can end while the route is quiet, and a quiet route sends only
    the keepalive: a reader that stops only after a real line holds its connection
    open for as long as the process lives."""
    response = EndlessResponse("the last line\n")
    _serve_in_order(monkeypatch, response)

    async def one_line():
        async for line in _reader().lines():
            return line

    assert asyncio.run(one_line()) == "the last line"
    deadline = time.monotonic() + 2
    while not response.is_closed and time.monotonic() < deadline:
        time.sleep(0.01)
    assert response.is_closed, "the route was left open after its reader was let go"


def test_a_reader_that_is_let_go_breaks_a_read_that_is_waiting(monkeypatch):
    """A quiet route sends nothing for fifteen seconds. A session that ends inside that silence
    cannot wait for it: the read in flight is broken, and the connection goes with it.
    """
    response = BlockingResponse()
    _serve_in_order(monkeypatch, response)

    async def read_and_let_go():
        reader = _reader()
        generator = reader.lines()
        waiting = asyncio.ensure_future(generator.__anext__())
        while not response.reading.is_set():
            await asyncio.sleep(0.01)
        waiting.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await waiting
        await generator.aclose()

    asyncio.run(read_and_let_go())
    assert (
        response.broken.is_set()
    ), "the read was left waiting for a line that may never come"
    deadline = time.monotonic() + 2
    while not response.is_closed and time.monotonic() < deadline:
        time.sleep(0.01)
    assert response.is_closed, "the route outlived the reader that was let go"


class FakeChat:
    """A chat task with the two registration methods `replace_registration` uses."""

    def __init__(self):
        self.triggers = []

    def append_trigger(self, item):
        self.triggers.append(item)

    def remove_trigger(self, item):
        self.triggers.remove(item)


def _looks_often(monkeypatch, seconds=0.01):
    """Look at the setting often enough for a test to see it move."""
    monkeypatch.setattr(feature, "RECHECK_SECONDS", seconds)


class Box:
    """A page's text box: the lines written into it, then silence until let go."""

    made: "list[Box]" = []

    def __init__(self, url, headers, loop):
        self.url = url
        self.closed = False
        self.written: "asyncio.Queue[str]" = asyncio.Queue()
        Box.made.append(self)

    async def lines(self):
        try:
            while True:
                yield await self.written.get()
        finally:
            self.closed = True


def _open_chat(monkeypatch):
    Box.made = []
    monkeypatch.setattr(feature, "RemoteTyped", Box)
    chat = FakeChat()
    enable_typed_input(chat)
    return chat


def test_without_the_setting_nothing_is_read(monkeypatch):
    """No server named, no route opened: the box belongs to the page that holds the
    microphone, and there is no such page yet."""
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", raising=False)
    _looks_often(monkeypatch)
    chat = _open_chat(monkeypatch)

    async def look():
        trigger = chat.triggers[0]()
        waiting = asyncio.ensure_future(trigger.__anext__())
        await asyncio.sleep(0.05)
        assert not waiting.done(), "a line was delivered with no server named"
        waiting.cancel()
        with contextlib.suppress(BaseException):
            await waiting
        await trigger.aclose()

    asyncio.run(look())
    assert Box.made == [], "a box was opened with no server named"


def test_the_box_opens_when_the_setting_arrives_after_the_chat_started(monkeypatch):
    """`/set LLM_VOICE_REMOTE_URL ...` moves the speaker and the microphone without a
    restart, and a box that only read the setting once left typing behind."""
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", raising=False)
    _looks_often(monkeypatch)
    chat = _open_chat(monkeypatch)

    async def type_after_setting():
        trigger = chat.triggers[0]()
        waiting = asyncio.ensure_future(trigger.__anext__())
        await asyncio.sleep(0.05)
        assert Box.made == [], "a box was opened before any server was named"
        monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", REMOTE_URL)
        while not Box.made:
            await asyncio.sleep(0.01)
        Box.made[0].written.put_nowait("typed after the setting moved")
        return await waiting

    item = asyncio.run(type_after_setting())

    assert item.text == "typed after the setting moved"
    assert item.source is WEB_INPUT


def test_the_box_follows_the_setting_to_another_server(monkeypatch):
    """One box at a time: the reader for the server that was named is let go before the
    one for the server named now is opened, or two readers would split a message."""
    first = "http://127.0.0.1:7777"
    second = "http://127.0.0.1:8888"
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", first)
    _looks_often(monkeypatch)
    chat = _open_chat(monkeypatch)

    async def move_the_voice():
        trigger = chat.triggers[0]()
        waiting = asyncio.ensure_future(trigger.__anext__())
        while not Box.made:
            await asyncio.sleep(0.01)
        Box.made[0].written.put_nowait("from the first server")
        before = await waiting
        waiting = asyncio.ensure_future(trigger.__anext__())
        monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", second)
        while len(Box.made) < 2:
            await asyncio.sleep(0.01)
        Box.made[1].written.put_nowait("from the second server")
        after = await waiting
        await trigger.aclose()
        return before, after

    before, after = asyncio.run(move_the_voice())

    assert [moved.url for moved in Box.made] == [first, second]
    assert Box.made[0].closed, "the reader for the server that was named is still open"
    assert (before.text, after.text) == (
        "from the first server",
        "from the second server",
    )


def test_a_page_without_a_box_is_not_asked_again(monkeypatch):
    """A reader that ends has said the page has no such route; asking a second later
    would get the same answer, so the setting is waited on instead."""
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", REMOTE_URL)
    _looks_often(monkeypatch)

    class NoBox:
        made = 0

        def __init__(self, url, headers, loop):
            NoBox.made += 1

        async def lines(self):
            return
            yield ""  # an async generator that ends at once, as a 404 route does

    monkeypatch.setattr(feature, "RemoteTyped", NoBox)
    chat = FakeChat()
    enable_typed_input(chat)

    async def look():
        trigger = chat.triggers[0]()
        waiting = asyncio.ensure_future(trigger.__anext__())
        await asyncio.sleep(0.1)  # many looks at the setting
        assert not waiting.done()
        waiting.cancel()
        with contextlib.suppress(BaseException):
            await waiting
        await trigger.aclose()

    asyncio.run(look())
    assert NoBox.made == 1, f"a page with no box was asked {NoBox.made} times"


def test_letting_the_trigger_go_closes_the_box(monkeypatch):
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", REMOTE_URL)
    _looks_often(monkeypatch)
    chat = _open_chat(monkeypatch)

    async def open_then_go():
        trigger = chat.triggers[0]()
        waiting = asyncio.ensure_future(trigger.__anext__())
        while not Box.made:
            await asyncio.sleep(0.01)
        waiting.cancel()
        with contextlib.suppress(BaseException):
            await waiting
        await trigger.aclose()

    asyncio.run(open_then_go())
    assert Box.made[0].closed, "the box outlived the trigger that opened it"


def test_a_typed_line_becomes_a_turn_of_its_own(monkeypatch):
    """Provenance is the web's, because it was typed rather than said: the turn
    says where it came from without being presented as transcription."""
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", REMOTE_URL)
    _looks_often(monkeypatch)

    class Reader:
        def __init__(self, url, headers, loop):
            self.url = url

        async def lines(self):
            yield "typed on the phone"

    monkeypatch.setattr(feature, "RemoteTyped", Reader)
    chat = FakeChat()
    enable_typed_input(chat)

    async def collect():
        trigger = chat.triggers[0]()
        return await trigger.__anext__()

    item = asyncio.run(collect())

    assert item.text == "typed on the phone"
    assert item.source is WEB_INPUT
