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


class ProbingBackend(WarmingBackend):
    """A backend whose warm-up probe always fails."""

    def __init__(self):
        super().__init__()
        self.probed = threading.Event()
        self.let_go = 0

    def create_audio(self, text):
        self.probed.set()
        raise RuntimeError("the model is not loaded")

    def close(self):
        self.let_go += 1


def test_a_failed_warm_up_is_not_a_failed_sentence(lock_file):
    """A warm-up runs at the start of every turn and loads the model once. A
    probe that fails must not count toward dropping the backend the turn's
    sentences are spoken by, and must not drop it from another thread while
    those sentences are made."""
    backend = ProbingBackend()
    speaker = Speaker(_config(backend, lock_file))

    for _ in range(3):
        speaker.warm_up()

    assert backend.probed.wait(5)
    assert backend.let_go == 0


class SlowBackend(WarmingBackend):
    """A backend whose model is loading: `create_audio` is where it waits."""

    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def create_audio(self, text):
        self.entered.set()
        self.release.wait(5)
        return super().create_audio(text)


def test_a_warm_up_already_loading_is_not_started_again(lock_file):
    """Every turn asks for one, and the model loads once: a turn asking while
    it loads waits for nothing and starts nothing — one chat had 38 of these
    threads parked behind the same load."""
    backend = SlowBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.warm_up()
    assert backend.entered.wait(5)
    speaker.warm_up()
    speaker.warm_up()
    backend.release.set()

    assert backend.closed.wait(5)
    time.sleep(0.2)
    assert backend.made == ["Hi."]


class CountingSlowBackend(SlowBackend):
    """A backend whose load parks, counting how many probes were asked for."""

    def __init__(self):
        super().__init__()
        self.starts = 0

    def create_audio(self, text):
        self.starts += 1
        return super().create_audio(text)


def test_a_restart_while_a_warm_up_is_parked_starts_no_second_one(lock_file):
    """A restart re-armed the guard, so a load that never finished cost a
    thread per turn: 38 parked threads on one chat, which is what the guard
    was written for. The set it is warming is gone, but the thread is not."""
    backend = CountingSlowBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.warm_up()
    assert backend.entered.wait(5)
    for _ in range(3):
        speaker.restart_backends()
        speaker.warm_up()
    time.sleep(0.2)

    assert backend.starts == 1
    backend.release.set()


def test_a_restarted_backend_set_is_warmed_again(lock_file):
    """A set of backends dropped and built again holds other models, so the
    turn after the restart warms them."""
    backend = WarmingBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.warm_up()
    assert backend.closed.wait(5)
    backend.closed.clear()
    speaker.restart_backends()
    speaker.warm_up()

    assert backend.closed.wait(5)
    assert backend.made == ["Hi.", "Hi."]


def test_a_warm_up_the_restart_overtook_does_not_mark_the_fresh_set_warm(lock_file):
    """A warm-up still running when the set is dropped warmed models the fresh
    set does not hold. Its completion must leave the flag down, or the turn
    after it is the one that loads the model synchronously."""
    backend = SlowBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.warm_up()
    assert backend.entered.wait(5)
    speaker.restart_backends()
    backend.release.set()
    assert backend.closed.wait(5)  # the overtaken warm-up finished

    backend.closed.clear()
    speaker.warm_up()

    assert backend.closed.wait(5)  # the fresh set was warmed after all
    assert backend.made == ["Hi.", "Hi."]


def test_a_warm_up_the_restart_overtook_does_not_warm_the_fresh_set(
    lock_file, monkeypatch
):
    """Warming the set that replaced it is the next `warm_up`'s work: doing it
    here too would probe one backend from two threads and load its model
    twice, which is what the warm-up was made once-per-set to avoid."""
    built = WarmingBackend()
    building, release = threading.Event(), threading.Event()

    def build(name, config):
        building.set()
        release.wait(5)
        return built

    monkeypatch.setattr("zrb.llm.speech.player.get_speech_backend", build)
    speaker = Speaker(_config("configured", lock_file))

    speaker.warm_up()
    assert building.wait(5)  # the warm-up is inside the build
    speaker.restart_backends()  # ... and the set it was started for is gone
    release.set()
    time.sleep(0.2)  # let the overtaken warm-up finish

    assert built.made == []  # it warmed nothing
    speaker.warm_up()

    assert built.closed.wait(5)
    assert built.made == ["Hi."]  # warmed once, by the set that is current


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
