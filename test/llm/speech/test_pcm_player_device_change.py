"""`PcmUtterance` and a device that changed under the process: PortAudio is
started again, so a sentence plays in its own voice on the device the machine
has now rather than going unsaid."""

import threading
import time
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from zrb.llm.speech import pcm_player
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.pcm_player import PcmUtterance

from .test_pcm_player import RATE, FakeOutputStream, _pcm, _played

np = pytest.importorskip("numpy")


@pytest.fixture(autouse=True)
def no_default_output_is_told_apart():
    """The machine's default output is read from the system, which a test does
    not have: nothing is told apart, and no sentence's device is remembered
    from another test, unless a test says what to read."""
    with (
        patch.object(pcm_player, "read_system_default_output", lambda sd: None),
        patch.object(pcm_player, "read_portaudio_default_output", lambda sd: None),
        patch.object(pcm_player, "_default_output", None),
    ):
        yield


@contextmanager
def _the_machine_plays_on(system: "str | None", port_audio: "str | None"):
    """The output the machine is set to play on, and the one PortAudio opens
    without being asked for a device."""
    with (
        patch.object(pcm_player, "read_system_default_output", lambda sd: system),
        patch.object(
            pcm_player, "read_portaudio_default_output", lambda sd: port_audio
        ),
    ):
        yield


class StaleDevice:
    """PortAudio after a headset went away: the devices it lists, and the
    default output among them, are the ones it was started with, so an open
    fails until it is started again."""

    def __init__(self, is_stale: bool = True, is_restartable: bool = True):
        self.is_stale = is_stale
        self.restarts = 0
        self.attempts = 0
        self.OutputStream = self._open
        if is_restartable:
            self._terminate = self._stop_portaudio
            self._initialize = self._start_portaudio

    def _open(self, **options):
        self.attempts += 1
        if self.is_stale:
            raise OSError("no default output device")
        return FakeOutputStream(**options)

    def _stop_portaudio(self):
        pass

    def _start_portaudio(self):
        self.restarts += 1
        self.is_stale = False


def _patched(device):
    FakeOutputStream.instances = []
    return patch.dict("sys.modules", {"sounddevice": device})


@pytest.fixture
def stale():
    device = StaleDevice()
    with _patched(device):
        yield device


@pytest.fixture
def healthy():
    device = StaleDevice(is_stale=False)
    with _patched(device):
        yield device


def test_an_open_that_fails_reads_the_devices_again(stale):
    """A headset unplugged after PortAudio started leaves its default output
    naming a device that is gone: the sentence reads the devices again instead
    of going unsaid."""
    utterance = PcmUtterance(SpeechAudio(RATE, [_pcm([7] * 256)]))

    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    assert stale.restarts == 1
    assert _played(stream)[:256].tolist() == [7] * 256


def test_a_resting_device_is_read_again_before_it_is_opened(stale):
    """The sentence made before the failure asks when it plays, by which time
    the devices have moved: they are read again before the first attempt, not
    after it fails."""
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([7] * 256)]), device_is_resting=lambda: True
    )

    utterance.play(timeout=5)

    assert (stale.restarts, stale.attempts) == (1, 1)
    assert _played(FakeOutputStream.instances[0])[:256].tolist() == [7] * 256


def test_a_device_that_plays_is_not_read_again(healthy):
    """Nothing is restarted for a device that works: the list PortAudio was
    started with is the right one, and starting it again is what costs."""
    utterance = PcmUtterance(SpeechAudio(RATE, [_pcm([7] * 256)]))

    utterance.play(timeout=5)

    assert (healthy.restarts, healthy.attempts) == (0, 1)


def test_the_devices_are_not_read_again_while_a_stream_plays(stale):
    """Starting PortAudio again stops every stream it has, so a device that
    fails while another sentence still plays keeps its failure."""
    playing = threading.Event()

    class SlowStream(FakeOutputStream):
        def start(self):
            super().start()
            playing.set()

        def _run(self):
            for _ in range(3):
                out = np.zeros((self.blocksize, 1), np.int16)
                self.callback(out, self.blocksize, None, None)
                self.played.append(out.copy())
                time.sleep(0.15)
            self.finished()

    def open_stream(**options):
        if stale.is_stale:
            raise OSError("no default output device")
        return SlowStream(**options)

    stale.OutputStream = open_stream
    # The device works for the first sentence: what is counted here is the
    # restart a failure while it still plays must not do.
    stale.is_stale = False
    playing_sentence = PcmUtterance(
        SpeechAudio(RATE, [_pcm([7] * 1024)] * 3), block_frames=1024
    )
    player = threading.Thread(target=playing_sentence.play, args=(5,))
    player.start()
    assert playing.wait(5), "the first sentence never started playing"
    stale.is_stale = True  # the device went away under the stream still playing

    with pytest.raises(OSError):
        PcmUtterance(SpeechAudio(RATE, [_pcm([7] * 256)])).play(timeout=1)
    player.join(5)

    assert stale.restarts == 0


class GoneOutputStream(FakeOutputStream):
    """A stream whose device PortAudio took away: never active, no block asked
    for, and nothing saying it finished."""

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        self.is_closed = True


def test_a_device_the_stream_lost_is_reported_with_nothing_to_take_over(stale):
    """The sentence after it has to open the devices the machine has now, so
    the loss is reported even where no player program can take the sentence."""
    stale.is_stale = False
    stale.OutputStream = GoneOutputStream
    told = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([7] * 256)]), on_device_error=told.append
    )

    utterance.play(timeout=2)

    [error] = told
    assert "unplugged or changed" in str(error)


def test_an_open_that_fails_is_reported_with_nothing_to_take_over():
    """A local voice has no second voice to hand its sentence to, and the log
    it would otherwise leave is behind the full-screen chat: the failure is
    said to the caller either way."""
    told = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([7] * 256)]), on_device_error=told.append
    )

    with _patched(StaleDevice(is_restartable=False)):
        with pytest.raises(OSError, match="no default output device"):
            utterance.play(timeout=1)

    assert [type(error) for error in told] == [OSError]


def test_a_device_that_cannot_be_read_again_keeps_the_failure_it_had():
    """A PortAudio that cannot be started anew (an older sounddevice, one that
    fails to start) leaves the sentence with the error it had, not a crash."""
    utterance = PcmUtterance(SpeechAudio(RATE, [_pcm([7] * 256)]))

    with _patched(StaleDevice(is_restartable=False)):
        with pytest.raises(OSError, match="no default output device"):
            utterance.play(timeout=1)


def test_a_stream_follows_the_output_the_machine_made_default_again(healthy):
    """A headset put back in is made the default output again, and is in no
    list PortAudio has: left alone there, the sentence plays on the output that
    was the default when PortAudio started."""
    with _the_machine_plays_on("soundcore R50i NC", "MacBook Pro Speakers"):
        PcmUtterance(SpeechAudio(RATE, [_pcm([7] * 256)])).play(timeout=5)

    assert (healthy.restarts, healthy.attempts) == (1, 1)
    assert _played(FakeOutputStream.instances[0])[:256].tolist() == [7] * 256


def test_an_output_the_machine_and_portaudio_agree_on_is_not_read_again(healthy):
    """Nothing is started again where PortAudio already opens the output the
    machine plays on: starting it again stops every stream it has, and any
    microphone open through it."""
    with _the_machine_plays_on("MacBook Pro Speakers", "MacBook Pro Speakers"):
        PcmUtterance(SpeechAudio(RATE, [_pcm([7] * 256)])).play(timeout=5)

    assert healthy.restarts == 0


def test_a_default_output_that_cannot_be_read_is_not_followed(healthy):
    """Where the machine's default cannot be told — not macOS, or a read that
    fails — the sentence plays where it did."""
    with _the_machine_plays_on(None, "MacBook Pro Speakers"):
        PcmUtterance(SpeechAudio(RATE, [_pcm([7] * 256)])).play(timeout=5)

    assert healthy.restarts == 0


def test_a_disagreement_a_restart_does_not_settle_is_read_again_once(healthy):
    """PortAudio naming a device its own way leaves the two readings different
    after a restart: that is worth one restart, not one for every sentence
    said afterwards."""
    with _the_machine_plays_on("soundcore R50i NC", "MacBook Pro Speakers"):
        for _ in range(2):
            PcmUtterance(SpeechAudio(RATE, [_pcm([7] * 256)])).play(timeout=5)

    assert (healthy.restarts, healthy.attempts) == (1, 2)
