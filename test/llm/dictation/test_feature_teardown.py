"""What a dictation session's end leaves behind.

Closing a session is synchronous and runs wherever the session was being served,
while letting a backend go is neither: a Pipecat pipeline's worker belongs to the
loop that started it, and a recording the teardown interrupted reaches its
transcription afterwards. This file is that end — where the backend is closed,
and what is refused once the session is over — while recording, listening,
barge-in and the commands stay in the sibling `test_feature*` files. Like them,
it carries its own copy of the fixtures: a test file is a feature group, not a
library.
"""

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
    """A synchronous teardown must not drop a backend on the floor.

    `close` is registered as a feature teardown, and it is synchronous where a
    backend's own close is not. Scheduling that close when no loop is running
    fails, and the coroutine left behind only warns once it is collected —
    with whatever model or pipeline the backend was holding still alive. The
    close is run to completion instead.
    """
    backend = ClosingBackend()
    session = DictationSession(DictationConfig(backend=backend).resolve())
    assert session.backend is backend  # built, and now the session's to let go

    session.close()

    assert backend.closed


def test_a_backend_bound_to_a_loop_is_closed_on_that_loop():
    """A synchronous teardown closes the backend where closing works.

    A Pipecat pipeline's worker is a task on the loop that started it. Closing
    from a loop of the teardown's own — what a synchronous close does when there
    is no loop to schedule on — makes that close await a task belonging to
    another loop, which raises the error `close_quietly` swallows: the session
    reports the backend let go while the worker, the pipeline and the model run
    on.
    """
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
    """A teardown with nowhere to close lets the backend go anyway.

    The loop that owns a pipeline can be gone by the time the session ends. A
    close run on a loop of the teardown's own cannot stop a worker that belongs
    to another one, so the backend is not closed from here — but leaving it where
    it stands, holding a model behind a reference this teardown is about to drop,
    is what a leak looks like. It is asked to release what it holds, and the
    teardown says the worker could not be stopped.
    """
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


@pytest.mark.asyncio
async def test_a_session_ended_mid_recording_builds_no_second_backend(monkeypatch):
    """The recording carries on into the teardown, and stops at it.

    A session ends while the microphone is open — the user leaves, a web socket
    drops. Stopping the recording releases the audio it had, which reaches the
    transcription after the backend has already been let go: a session that
    transcribes it anyway is asking for a backend the closing never saw, and one
    holding a model and a pipeline nobody will close.
    """
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
