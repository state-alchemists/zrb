"""Dictation session teardown closes backends on their owning loops."""

import asyncio
import logging
import threading

import pytest

from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import Utterance


class FakeBackend(AnyDictationBackend):
    """Transcribes each clip to the text it was built from."""

    def __init__(self):
        self.transcribed: list[bytes] = []

    async def transcribe(self, audio: bytes) -> str:
        self.transcribed.append(audio)
        return audio.decode()


class ClosingBackend(FakeBackend):
    """A backend that says when it was let go."""

    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeUI:
    def __init__(self):
        self.background_tasks: set = set()
        self.outputs: list[str] = []
        self.inserted: list[str] = []

    def set_status_badge(self, key, text):
        pass

    def append_to_output(self, text):
        self.outputs.append(text)

    def insert_input_text(self, text):
        self.inserted.append(text)


def test_closing_a_session_where_no_loop_runs_still_closes_the_backend():
    """Synchronous teardown runs an async close to completion without a loop."""
    backend = ClosingBackend()
    session = DictationSession(DictationConfig(backend=backend).resolve())
    assert session.backend is backend  # built, and now the session's to let go

    session.close()

    assert backend.closed


def test_a_backend_bound_to_a_loop_is_closed_on_that_loop():
    """Teardown closes a loop-bound backend on its owning loop."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    closed = threading.Event()
    closed_on: "list[object]" = []

    class LoopBound(AnyDictationBackend):
        @property
        def owner_loop(self):
            return loop

        async def transcribe(self, audio: bytes) -> str:
            return ""

        async def aclose(self) -> None:
            closed_on.append(asyncio.get_running_loop())
            closed.set()

    try:
        session = DictationSession(DictationConfig().resolve())
        session.backend = LoopBound()
        session.close()

        assert closed.wait(5)
        assert closed_on == [loop]
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)
        loop.close()


def test_a_backend_whose_loop_is_gone_is_released_and_reported(caplog):
    """A backend on a gone loop is released and reported as uncloseable."""
    loop = asyncio.new_event_loop()
    loop.close()
    closed: "list[object]" = []
    released: "list[object]" = []

    class Abandoned(AnyDictationBackend):
        @property
        def owner_loop(self):
            return loop

        async def transcribe(self, audio: bytes) -> str:
            return ""

        def release(self) -> None:
            released.append(True)

        async def aclose(self) -> None:
            closed.append(True)

    session = DictationSession(DictationConfig().resolve())
    session.backend = Abandoned()

    with caplog.at_level(logging.WARNING, logger="zrb.llm.dictation.feature"):
        session.close()

    assert closed == []
    assert released == [True]
    assert "not running" in caplog.text


def test_a_loop_that_stops_during_the_handoff_still_lets_the_backend_go(
    monkeypatch, caplog
):
    """A loop stopping during handoff still releases the backend."""
    loop = asyncio.new_event_loop()
    loop.close()
    # Simulate a loop closing between the running check and callback handoff.
    monkeypatch.setattr(loop, "is_running", lambda: True)
    released: "list[object]" = []

    class Abandoned(AnyDictationBackend):
        @property
        def owner_loop(self):
            return loop

        async def transcribe(self, audio: bytes) -> str:
            return ""

        def release(self) -> None:
            released.append(True)

        async def aclose(self) -> None:
            raise AssertionError("a loop that takes no callback cannot run this")

    session = DictationSession(DictationConfig().resolve())
    session.backend = Abandoned()

    with caplog.at_level(logging.WARNING, logger="zrb.llm.dictation.feature"):
        session.close()

    assert released == [True]
    assert "not running" in caplog.text


@pytest.mark.asyncio
async def test_a_session_ended_mid_recording_builds_no_second_backend(monkeypatch):
    """Ending mid-recording does not build a second backend for released audio."""
    stopped = asyncio.Event()
    built: list[object] = []
    backend = FakeBackend()

    async def listen(
        config,
        should_listen,
        keep_partial=False,
        on_state=None,
        on_barge_in=None,
        **kwargs,
    ):
        while should_listen():
            await asyncio.sleep(0)
        stopped.set()
        yield Utterance(b"half a sentence", 0.0, 1.0)

    def get_backend(name, config):
        built.append(name)
        return backend

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    monkeypatch.setattr("zrb.llm.dictation.feature.get_dictation_backend", get_backend)
    session = DictationSession(
        DictationConfig(backend="moonshine", commands=["/voice"]).resolve()
    )
    ui = FakeUI()

    session.create_commands()[0].handle({}, ui)
    await asyncio.sleep(0)
    session.close()
    await asyncio.gather(*ui.background_tasks)

    assert stopped.is_set()
    assert backend.transcribed == []
    assert built == ["moonshine"]  # the one the command made, and no other
    assert ui.inserted == []


@pytest.mark.asyncio
async def test_a_session_that_ends_lets_its_backend_go():
    """Synchronous close schedules async backend release on the running loop."""
    backend = ClosingBackend()
    session = DictationSession(DictationConfig().resolve())
    session.backend = backend

    session.close()
    await asyncio.sleep(0)

    assert backend.closed


@pytest.mark.asyncio
async def test_closing_a_session_that_never_dictated_builds_nothing(monkeypatch):
    """A session that never dictates builds no backend to close."""
    built: list[str] = []
    monkeypatch.setattr(
        "zrb.llm.dictation.feature.get_dictation_backend",
        lambda name, config: built.append(name),
    )
    session = DictationSession(DictationConfig().resolve())

    session.close()
    await asyncio.sleep(0)

    assert built == []
