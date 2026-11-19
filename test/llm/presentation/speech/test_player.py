"""Pin how a sentence is played and how it stops: a backend that fails hands it
to the local engine, the speaking flag outlives a second speaker, and close,
drain or a ctrl-c cuts off what is playing. The page that owns the voice is
where the last two tests send it, so nothing here says the sentence twice."""

import atexit
import threading

import pytest

from zrb.config.config import CFG
from zrb.llm.presentation.speech import (
    AnySpeechBackend,
    Speaker,
    Utterance,
)
from zrb.llm.presentation.speech.player import is_speaking, play
from zrb.util.file_lock import hold_file_lock

from .player_support import (
    FakeBackend,
    HangingBackend,
    _config,
)


class BrokenUtterance(Utterance):
    def play(self, timeout):
        raise OSError("device gone")


class BrokenPlayerBackend(AnySpeechBackend):
    def create_utterance(self, text):
        return BrokenUtterance([])


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
        "zrb.llm.presentation.speech.backend.utterance.subprocess.Popen", FinishedPopen
    )
    speaker = Speaker(_config(FakeBackend(fail=True), lock_file, voice="alloy"))

    speaker.speak("hello")

    # The requested backend's voice is not passed to the fallback.
    assert runs == [["espeak-ng", "-s", "165", "-v", "en-us+m3", "--", "hello"]]


def test_nothing_is_spoken_when_every_backend_fails(lock_file, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    backend = FakeBackend(fail=True)

    with pytest.raises(RuntimeError, match="FakeBackend: no network"):
        Speaker(_config(backend, lock_file)).speak("hello")

    assert backend.played == []


def test_a_failing_player_raises_and_releases_the_lock(lock_file):
    with pytest.raises(OSError, match="device gone"):
        play(BrokenUtterance([]), _config(FakeBackend(), lock_file))

    assert not is_speaking(lock_file)


def test_a_failing_player_in_the_queue_is_logged_not_raised(lock_file, caplog):
    speaker = Speaker(_config(BrokenPlayerBackend(), lock_file))

    speaker.say("hello")
    speaker.drain()

    assert "Speech failed: device gone" in caplog.text


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


def test_a_lock_file_is_only_forgotten_once_every_speaker_using_it_is(lock_file):
    first = Speaker(_config(FakeBackend(), lock_file))
    second = Speaker(_config(FakeBackend(), lock_file))

    first.close()
    with hold_file_lock(lock_file):
        assert is_speaking()

    second.close()
    with hold_file_lock(lock_file):
        assert not is_speaking()


def test_close_cuts_off_what_is_playing(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=5))
    speaker.say("a long reply")
    assert backend.started.wait(5)

    speaker.close()

    assert backend.utterances[0].stopped.is_set()


def test_drain_cuts_off_what_outlives_its_timeout(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=0.05))
    speaker.say("a long reply")
    assert backend.started.wait(5)

    speaker.drain()

    assert backend.utterances[0].stopped.is_set()


def test_ctrl_c_during_drain_still_cuts_off_what_is_playing(lock_file, monkeypatch):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=5))
    speaker.say("a long reply")
    assert backend.started.wait(5)

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
    assert backend.started.wait(5)

    def interrupted_join(self, timeout=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(threading.Thread, "join", interrupted_join)
    for exit_hook in registered:
        exit_hook()

    assert backend.utterances[0].stopped.is_set()


def test_where_the_voice_is_the_page_nothing_here_says_the_sentence(
    lock_file, monkeypatch
):
    """`LLM_VOICE_REMOTE_URL` is the one setting that moves the voice, and it
    moves it whole: a backend that made no audio zrb could post has no stand-in
    on this machine, so the sentence goes unsaid rather than out of a speaker
    here — which would say it in a second room."""
    monkeypatch.setenv(
        f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", "http://127.0.0.1:7777"
    )
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.say("a sentence for the page")
    speaker.drain()

    assert backend.utterances == []


def test_where_the_voice_is_the_page_it_is_played_in_process(lock_file, monkeypatch):
    """Even with a player program asked for, the page's speaker is where the
    voice goes: a program here would play it a second time."""
    monkeypatch.setenv(
        f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", "http://127.0.0.1:7777"
    )
    speaker = Speaker(_config(FakeBackend(), lock_file))  # player: command

    assert speaker.is_playing_in_process
