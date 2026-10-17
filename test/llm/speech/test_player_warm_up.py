"""Speaker warm-up: a backend's model loads before the first sentence."""

import threading
import time

import pytest

from zrb.llm.speech import AnySpeechBackend, Speaker, SpeechConfig
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.player import is_speaking


@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "speech.lock")


@pytest.fixture(autouse=True)
def in_process(monkeypatch):
    """Play in process, as a machine with an audio device does."""
    monkeypatch.setattr("zrb.llm.speech.player.is_in_process_available", lambda: True)


def _config(backend, lock_file, player="auto"):
    return SpeechConfig(
        backend=backend, lock_file=lock_file, lock_timeout=0.05, player=player
    ).resolve()


class WarmingBackend(AnySpeechBackend):
    """A local backend zrb plays itself, recording what it was asked to make."""

    def __init__(self):
        self.made: list[str] = []
        self.closed = threading.Event()

    @property
    def needs_zrb_playback(self) -> bool:
        return True

    @property
    def is_local(self) -> bool:
        return True

    def create_utterance(self, text):
        raise RuntimeError("plays in process only")

    def create_audio(self, text):
        self.made.append(text)
        return SpeechAudio(16000, [b"\x00\x00"], close=self.closed.set)


def test_warm_up_makes_one_word_it_never_plays(lock_file):
    backend = WarmingBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.warm_up()

    assert backend.closed.wait(5)
    assert backend.made == ["Hi."]
    assert not is_speaking(lock_file)


def test_warm_up_failing_is_left_to_the_first_sentence(lock_file):
    backend = WarmingBackend()
    backend.create_audio = lambda text: (_ for _ in ()).throw(RuntimeError("no model"))
    speaker = Speaker(_config(backend, lock_file))

    speaker.warm_up()
    time.sleep(0.2)

    assert backend.made == []


class CloudBackend(WarmingBackend):
    @property
    def needs_zrb_playback(self) -> bool:
        return False


def test_warm_up_leaves_a_voice_zrb_does_not_run_alone(lock_file):
    backend = CloudBackend()
    Speaker(_config(backend, lock_file)).warm_up()
    time.sleep(0.2)

    assert backend.made == []


class RemoteInProcessBackend(WarmingBackend):
    """A paid API whose audio zrb plays, like a registered cloud Pipecat voice."""

    @property
    def is_local(self) -> bool:
        return False


def test_warm_up_leaves_a_remote_voice_zrb_plays_alone(lock_file):
    backend = RemoteInProcessBackend()
    Speaker(_config(backend, lock_file)).warm_up()
    time.sleep(0.2)

    assert backend.made == []


def test_warm_up_logs_a_missing_package_instead_of_raising(lock_file, monkeypatch):
    raised = []
    monkeypatch.setattr(threading, "excepthook", raised.append)
    backend = WarmingBackend()
    backend.create_audio = lambda text: (_ for _ in ()).throw(ImportError("no torch"))
    Speaker(_config(backend, lock_file)).warm_up()
    time.sleep(0.2)

    assert raised == []


def test_warm_up_waits_for_a_player_program_to_be_unwanted(lock_file):
    backend = WarmingBackend()
    Speaker(_config(backend, lock_file, player="command")).warm_up()
    time.sleep(0.2)

    assert backend.made == []


class FallbackBackend(CloudBackend):
    """The local voice a speaker falls back to."""


def test_warm_up_never_falls_back_to_another_backend(lock_file, monkeypatch):
    failing = WarmingBackend()
    failing.create_audio = lambda text: (_ for _ in ()).throw(RuntimeError("no model"))
    fallback = FallbackBackend()
    monkeypatch.setattr(
        "zrb.llm.speech.player.get_speech_backend",
        lambda name, config: fallback if name == "auto" else failing,
    )
    speaker = Speaker(_config("configured", lock_file))

    speaker.warm_up()
    time.sleep(0.2)

    assert fallback.made == []
