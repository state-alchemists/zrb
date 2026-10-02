import atexit
import threading
import time

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
    # Played by a program unless a test says otherwise: these tests are about
    # queueing, locking and stopping, not where the audio goes.
    fields.setdefault("player", "command")
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

    class FinishedPopen:
        def __init__(self, argv, **kwargs):
            runs.append(argv)

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(
        "zrb.llm.speech.backend.utterance.subprocess.Popen", FinishedPopen
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


def test_dictation_hears_a_speaker_with_its_own_lock_file(tmp_path, lock_file):
    """is_speaking() without arguments is what dictation calls."""
    custom = str(tmp_path / "custom.lock")
    Speaker(_config(FakeBackend(), custom))

    with hold_file_lock(custom):
        assert is_speaking()
    assert not is_speaking()


def test_two_speakers_playing_at_once_keep_speaking_true(tmp_path):
    first_started, release_first = threading.Event(), threading.Event()
    seen_after_second = []

    class Blocking(Utterance):
        def play(self, timeout):
            first_started.set()
            release_first.wait(5)

    class Checking(Utterance):
        def play(self, timeout):
            pass

    first_config = _config(FakeBackend(), str(tmp_path / "a.lock"))
    second_config = _config(FakeBackend(), str(tmp_path / "b.lock"))
    worker = threading.Thread(target=play, args=(Blocking([]), first_config))
    worker.start()
    first_started.wait(5)

    play(Checking([]), second_config)
    seen_after_second.append(is_speaking())
    release_first.set()
    worker.join(5)

    # The second speaker finishing must not hide the first one still playing.
    assert seen_after_second == [True]
    assert not is_speaking()


def test_a_closed_speaker_stops_being_probed_for_its_lock_file(lock_file):
    """`is_speaking` probes every lock file a live speaker configured, once
    per captured audio block. A speaker that has gone away must stop being
    one, or a long-lived process keeps re-checking a dead session's path and
    stays muted whenever anything else holds it."""
    Speaker(_config(FakeBackend(), lock_file)).close()

    with hold_file_lock(lock_file):
        assert not is_speaking()


def test_a_lock_file_is_only_forgotten_once_every_speaker_using_it_is(lock_file):
    first = Speaker(_config(FakeBackend(), lock_file))
    second = Speaker(_config(FakeBackend(), lock_file))

    first.close()
    with hold_file_lock(lock_file):
        assert is_speaking()

    second.close()
    with hold_file_lock(lock_file):
        assert not is_speaking()


class HangingUtterance(Utterance):
    """Plays until stopped."""

    def __init__(self, started: threading.Event):
        super().__init__([])
        self.started = started
        self.stopped = threading.Event()
        self.is_played = False

    def play(self, timeout):
        self.is_played = True
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


def test_close_cuts_off_what_is_playing(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=5))
    speaker.say("a long reply")
    assert backend.started.wait(1)

    speaker.close()

    assert backend.utterances[0].stopped.is_set()


def test_drain_cuts_off_what_outlives_its_timeout(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=0.05))
    speaker.say("a long reply")
    assert backend.started.wait(1)

    speaker.drain()

    assert backend.utterances[0].stopped.is_set()


def test_ctrl_c_during_drain_still_cuts_off_what_is_playing(lock_file, monkeypatch):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=5))
    speaker.say("a long reply")
    assert backend.started.wait(1)

    def interrupted_join(self, timeout=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(threading.Thread, "join", interrupted_join)
    with pytest.raises(KeyboardInterrupt):
        speaker.drain()

    assert backend.utterances[0].stopped.is_set()


def test_ctrl_c_during_the_exit_drain_cuts_off_without_a_traceback(
    lock_file, monkeypatch
):
    registered: list = []
    monkeypatch.setattr(atexit, "register", registered.append)
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=5))
    speaker.say("a long reply")
    assert backend.started.wait(1)

    def interrupted_join(self, timeout=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(threading.Thread, "join", interrupted_join)
    for exit_hook in registered:
        exit_hook()

    assert backend.utterances[0].stopped.is_set()


def test_a_closed_speaker_says_nothing(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.close()

    speaker.say("too late")
    speaker.drain()

    assert backend.played == []


def test_speech_created_after_close_is_never_played(lock_file):
    """A backend still synthesizing when the session closes."""
    created = threading.Event()
    release = threading.Event()

    class SlowBackend(FakeBackend):
        def create_utterance(self, text):
            created.set()
            release.wait(5)
            return super().create_utterance(text)

    backend = SlowBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.say("slow")
    assert created.wait(1)

    speaker.close()
    release.set()
    time.sleep(0.1)

    assert backend.played == []
    assert backend.utterances[0].cleaned


def test_text_said_later_keeps_its_place_and_is_waited_for_at_exit(lock_file):
    """A summary queued at the end of `zrb chat --message` must be spoken
    before the process exits, and before what was queued after it."""
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=5))

    speaker.say_later(lambda: time.sleep(0.05) or "the summary")
    speaker.say("the approval")
    speaker.drain()

    assert backend.played == ["the summary", "the approval"]


def test_text_said_later_is_dropped_when_the_speaker_closes(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))
    producing = threading.Event()
    release = threading.Event()

    def produce():
        producing.set()
        release.wait(5)
        return "too late"

    speaker.say_later(produce)
    assert producing.wait(1)
    speaker.close()
    release.set()
    time.sleep(0.1)

    assert backend.played == []


def test_stale_text_is_skipped(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.say("stale", is_stale=lambda: True)
    speaker.say("fresh")

    assert backend.done.wait(1)
    speaker.drain()
    assert backend.played == ["fresh"]


def test_text_going_stale_while_playing_is_cut_off(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file))
    answered = threading.Event()
    speaker.say("approve this?", is_stale=answered.is_set)
    assert backend.started.wait(1)

    answered.set()

    assert backend.utterances[0].stopped.wait(1)
    speaker.close()


def test_interrupt_stops_what_is_playing_and_drops_the_queue(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=1))
    speaker.say("a long reply")
    speaker.say("queued behind it")
    assert backend.started.wait(1)

    speaker.interrupt()
    speaker.drain()

    assert backend.utterances[0].stopped.is_set()
    # Made ahead while the first played, but never played.
    assert [u.is_played for u in backend.utterances] in ([True], [True, False])


def test_speech_being_made_when_interrupted_is_dropped(lock_file):
    created = threading.Event()
    release = threading.Event()

    class SlowBackend(FakeBackend):
        def create_utterance(self, text):
            if text == "slow":
                created.set()
                release.wait(5)
            return super().create_utterance(text)

    backend = SlowBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.say("slow")
    assert created.wait(1)

    speaker.interrupt()
    release.set()
    speaker.say("after")
    speaker.drain()

    assert backend.played == ["after"]
    assert backend.utterances[0].cleaned


def test_the_next_sentence_is_made_while_the_current_one_plays(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=0.2))
    speaker.say("first")
    speaker.say("second")
    assert backend.started.wait(1)

    deadline = time.monotonic() + 1
    while len(backend.utterances) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert len(backend.utterances) == 2
    assert not backend.utterances[1].is_played
    speaker.close()
