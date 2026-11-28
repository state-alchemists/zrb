"""The page's text box as a chat feature: which server it follows, and what a line becomes.

The reader itself -- one long GET, reconnected, blank lines dropped -- is tested beside this in
`test_remote_typed.py`, with the fake responses it needs. Here the reader is a fake, and what is
being tested is the trigger: that it opens when the setting names a server and stops when it does
not, that it follows the setting while the chat runs (`/set LLM_VOICE_REMOTE_URL ...`), and that a
line it hands on is the user's own words, typed rather than said.
"""

import asyncio
import contextlib

from zrb.config.config import CFG
from zrb.llm.contracts.shared.input_source import WEB_INPUT
from zrb.llm.presentation.typed import feature
from zrb.llm.presentation.typed.feature import enable_typed_input

REMOTE_URL = "http://127.0.0.1:7777"


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


def test_a_server_that_had_no_box_is_asked_again_when_the_setting_returns(monkeypatch):
    """The answer is remembered only while the setting stays on that server: a page that had no box
    may be upgraded by the time the setting comes back to it."""
    first = "http://127.0.0.1:7777"
    second = "http://127.0.0.1:8888"
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", first)
    _looks_often(monkeypatch)

    class NoBox:
        asked: "list[str]" = []

        def __init__(self, url, headers, loop):
            NoBox.asked.append(url)

        async def lines(self):
            return
            yield ""

    monkeypatch.setattr(feature, "RemoteTyped", NoBox)
    chat = FakeChat()
    enable_typed_input(chat)

    async def come_back():
        trigger = chat.triggers[0]()
        waiting = asyncio.ensure_future(trigger.__anext__())

        async def until(count):
            for _ in range(100):
                if len(NoBox.asked) >= count:
                    return
                await asyncio.sleep(0.01)

        await until(1)
        monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", second)
        await until(2)
        monkeypatch.setenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", first)
        await until(3)
        waiting.cancel()
        with contextlib.suppress(BaseException):
            await waiting
        await trigger.aclose()

    asyncio.run(come_back())
    assert NoBox.asked == [
        first,
        second,
        first,
    ], "a server that had no box is never asked again, so a page upgraded since stays shut"


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
