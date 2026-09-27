import threading

import pytest

from zrb.llm.speech import AnySpeechBackend, Speaker, SpeechConfig, Utterance
from zrb.llm.speech.player import is_speaking, play
from zrb.util.file_lock import hold_file_lock


class RecordingUtterance(Utterance):
    def __init__(self, text: str, played: list[str], done: threading.Event):
        super().__init__([])
        self.text = text
        self.played = played
        self.done = done
        self.speaking_while_played: bool | None = None
        self.cleaned = False

    def play(self, timeout):
        self.speaking_while_played = is_speaking()
        self.played.append(self.text)
        self.done.set()

    def cleanup(self):
        self.cleaned = True


class FakeBackend(AnySpeechBackend):
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.played: list[str] = []
        self.done = threading.Event()
        self.utterances: list[RecordingUtterance] = []

    def create_utterance(self, text):
        if self.fail:
            raise RuntimeError("no network")
        utterance = RecordingUtterance(text, self.played, self.done)
        self.utterances.append(utterance)
        return utterance


@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "speech.lock")


def _config(backend, lock_file, **fields):
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, **fields
    ).resolve()


def test_queued_text_is_spoken_in_order_on_the_background_thread(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.say("one")
    speaker.say("two")
    speaker.drain()

    assert backend.played == ["one", "two"]
    assert all(u.speaking_while_played for u in backend.utterances)
    assert all(u.cleaned for u in backend.utterances)
    assert not is_speaking(lock_file)


def test_nothing_is_queued_while_disabled_or_blank(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.is_enabled = False

    speaker.say("muted")
    speaker.is_enabled = True
    speaker.say("   ")
    speaker.drain()

    assert backend.played == []


def test_clear_drops_what_is_not_yet_spoken(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    with hold_file_lock(lock_file):
        speaker.say("first")  # the thread blocks on the lock with this one
        speaker.say("stale")
        speaker.clear()
    speaker.drain()

    assert "stale" not in backend.played


def test_another_session_speaking_is_seen_and_waited_out(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    with hold_file_lock(lock_file):
        assert is_speaking(lock_file)
        speaker.speak("dropped")  # lock_timeout passes while it is held

    assert backend.played == []
    assert not is_speaking(lock_file)


def test_a_failing_backend_falls_back_to_the_local_engine(lock_file, monkeypatch):
    runs = []
    monkeypatch.setattr(
        "shutil.which", lambda name: f"/usr/bin/{name}" if name == "espeak-ng" else None
    )
    monkeypatch.setattr(
        "zrb.llm.speech.backend.utterance.subprocess.run",
        lambda argv, **kwargs: runs.append(argv),
    )
    speaker = Speaker(_config(FakeBackend(fail=True), lock_file, voice="alloy"))

    speaker.speak("hello")

    # The requested backend's voice is not passed to the fallback.
    assert runs == [["espeak-ng", "-s", "165", "-v", "en-us+m3", "--", "hello"]]


def test_nothing_is_spoken_when_every_backend_fails(lock_file, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    backend = FakeBackend(fail=True)

    Speaker(_config(backend, lock_file)).speak("hello")

    assert backend.played == []


def test_a_failing_player_is_logged_not_raised(lock_file):
    class Broken(Utterance):
        def play(self, timeout):
            raise OSError("device gone")

    play(Broken([]), _config(FakeBackend(), lock_file))

    assert not is_speaking(lock_file)
