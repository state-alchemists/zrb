"""A narration line is worth the seconds it takes to finish.

The staleness check that drops a line no longer worth saying used to cut a line
already being said, mid-sentence: two tool calls in a row chopped the voice
twice. These tests pin both halves — a line that has started finishes, a line
that has not is still dropped — and the wiring that asks for the first.

Split out of `test_player.py` and `test_feature.py`, which are at the
test-file budget (AGENTS.md → Test Guidelines).
"""

import threading
import time
from types import SimpleNamespace

import pytest

from zrb.llm.speech import AnySpeechBackend, Speaker, SpeechConfig, Utterance
from zrb.llm.speech.feature import SpeechSession


class HangingUtterance(Utterance):
    """Plays until something stops it."""

    def __init__(self, started: threading.Event):
        super().__init__([])
        self.started = started
        self.stopped = threading.Event()

    def play(self, timeout):
        self.started.set()
        self.stopped.wait(5)

    def stop(self):
        self.stopped.set()


class HangingBackend(AnySpeechBackend):
    def __init__(self):
        self.started = threading.Event()
        self.utterances: list[HangingUtterance] = []

    def create_utterance(self, text):
        utterance = HangingUtterance(self.started)
        self.utterances.append(utterance)
        return utterance


class RecordingSpeaker:
    """Remembers what it was asked to say, and whether the line may finish."""

    is_playing_in_process = True

    def __init__(self):
        self.said: list[str] = []
        self.cut_when_stale: list[bool] = []
        self.is_enabled = True
        self.volume = 100
        self.cleared = 0
        self.closed = 0
        self.restarted = 0

    def say(self, text, is_stale=None, voice="", cut_when_stale=True):
        self.said.append(text)
        self.cut_when_stale.append(cut_when_stale)

    def set_volume(self, percent):
        self.volume = percent

    def clear(self):
        self.cleared += 1

    def close(self):
        self.closed += 1

    def restart_backends(self):
        self.restarted += 1


@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "speech.lock")


def _config(backend, lock_file):
    # Played by a program: these tests are about stopping, not where audio goes.
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, player="command"
    ).resolve()


def test_a_line_asked_to_finish_is_not_cut_when_it_goes_stale(lock_file):
    """A tool finishing says nothing about the line being said about it."""
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file))
    finished = threading.Event()
    speaker.say("Checking the tests.", is_stale=finished.is_set, cut_when_stale=False)
    assert backend.started.wait(5)

    finished.set()
    time.sleep(0.3)  # three polls: the staleness check runs every 0.1 s

    assert not backend.utterances[0].stopped.is_set()
    speaker.close()


def test_a_tool_call_narration_is_queued_to_finish_its_sentence():
    """The session asks for the line to finish; only a reply, an approval or a
    question is cut when it stops mattering."""
    session = SpeechSession(
        SpeechConfig(enabled=True, events=["progress"], progress_interval=1).resolve()
    )
    session.speaker = RecordingSpeaker()
    try:
        session.handle_stream_event(
            SimpleNamespace(
                event_kind="function_tool_call",
                part=SimpleNamespace(
                    tool_name="Shell",
                    tool_call_id="call-1",
                    args={"purpose": "Listing the files"},
                ),
            )
        )

        assert session.speaker.said == ["Listing the files"]
        assert session.speaker.cut_when_stale == [False]
    finally:
        session.close()
