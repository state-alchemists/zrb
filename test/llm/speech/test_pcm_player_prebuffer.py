"""`ZRB_LLM_SPEECH_PLAYER_PREBUFFER_SECONDS`: how much audio the device starts
on, why the wait that holds it off has to grow with it, and what the cushion
buys — a stall in the engine that is absorbed instead of heard."""

import math
import queue
import threading
import time
import types
from dataclasses import fields
from unittest.mock import patch

import pytest

from zrb.config.config import CFG
from zrb.llm.speech.backend.audio import SpeechAudio
from zrb.llm.speech.config import SpeechConfig
from zrb.llm.speech.pcm_player import PcmUtterance, prebuffer_wait_seconds

from .test_pcm_player import (
    RATE,
    CallbackStop,
    FakeOutputStream,
    ProgramUtterance,
    _pcm,
    _played,
)
from .test_pcm_player_underrun import GoneOutputStream

np = pytest.importorskip("numpy")

# One block of the player's default size, and how long it plays for.
BLOCK = 1024
BLOCK_SECONDS = BLOCK / RATE
# Long enough to be heard, and short enough of the cushion under test (0.5)
# that absorbing it is not a tie.
STALL_SECONDS = 0.3


class TimedStream(FakeOutputStream):
    """A stream that says when its device started playing."""

    def start(self):
        self.started_at = time.monotonic()
        super().start()


class ManualStream(FakeOutputStream):
    """A device that plays a block only when the test says so: one `tick` is
    one block of playing time, so a stall is counted in blocks, not seconds."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_started = threading.Event()

    def start(self):
        self._running = True
        self.is_started.set()

    def tick(self):
        out = np.zeros((self.blocksize, 1), np.int16)
        self.callback(out, self.blocksize, None, None)


class ScriptedSource:
    """Audio that arrives only when the test feeds it, and says when the player
    has taken what was fed, so no step of the script depends on a clock."""

    def __init__(self):
        self._items = queue.Queue()
        self._asks = 0
        self._fed = 0
        self._asked = threading.Condition()

    def chunks(self):
        while True:
            with self._asked:
                self._asks += 1
                self._asked.notify_all()
            chunk = self._items.get(timeout=10)
            if chunk is None:
                return
            yield chunk

    def feed(self, chunk):
        """Hand over a chunk and wait until the player's reader holds it: the
        reader asking for the next one is what says it has.

        The reader pulls the next chunk from the source before it checks for
        room (`for chunk in chunks: if not has_room(): ...`), so it asks even
        when the buffer is full: feeding exactly the cushion's worth never
        waits on a request the full buffer would withhold."""
        self._fed += 1
        self._items.put(chunk)
        if chunk is not None:
            with self._asked:
                assert self._asked.wait_for(lambda: self._asks > self._fed, 10)


def _start_playing(prebuffer_seconds, **options):
    """A player on a source the test feeds, running on a thread of its own:
    the player, its source, the thread and the device it opened."""
    FakeOutputStream.instances = []
    source = ScriptedSource()
    utterance = PcmUtterance(
        SpeechAudio(RATE, source.chunks()),
        prebuffer_seconds=prebuffer_seconds,
        **options,
    )
    player = threading.Thread(target=utterance.play, args=(30,), daemon=True)
    player.start()
    while not FakeOutputStream.instances:  # the device is opened as play begins
        time.sleep(0.001)
    [stream] = FakeOutputStream.instances
    return utterance, source, player, stream


def _hang_up(utterance, source, player):
    source.feed(None)
    utterance.stop()
    player.join(10)


def _pausing_source(pause=STALL_SECONDS):
    """Audio that arrives, pauses, then arrives again: a render that stalled."""

    def chunks():
        yield _pcm([5] * 1600)
        time.sleep(pause)
        yield _pcm([5] * 1600)

    return chunks()


@pytest.fixture
def sd():
    FakeOutputStream.instances = []
    fake = types.SimpleNamespace(
        OutputStream=FakeOutputStream, CallbackStop=CallbackStop
    )
    with patch.dict("sys.modules", {"sounddevice": fake}):
        yield fake


def test_the_wait_grows_with_the_cushion():
    """A cushion longer than the old flat second must not be capped back to
    it: the wait is what the cushion has to be delivered inside."""
    assert prebuffer_wait_seconds(0.1) == 1.0
    assert prebuffer_wait_seconds(0.4) == 1.0
    assert prebuffer_wait_seconds(0.6) == pytest.approx(1.2)
    assert prebuffer_wait_seconds(3.0) == pytest.approx(6.0)
    for cushion in (0.05, 0.1, 0.4, 0.6, 1.0, 5.0):
        assert prebuffer_wait_seconds(cushion) >= cushion


def test_the_device_starts_on_the_audio_the_cushion_asks_for(sd):
    """The cushion decides how much audio stands by: a tenth of a second
    starts on the first chunk, half a second waits for the rest of it."""
    sd.OutputStream = ManualStream
    first = _pcm([5] * 1600)  # a tenth of a second

    utterance, source, player, thin = _start_playing(0.1, block_frames=BLOCK)
    source.feed(first)
    assert thin.is_started.wait(10)  # started on the first chunk alone
    _hang_up(utterance, source, player)

    utterance, source, player, deep = _start_playing(0.5, block_frames=BLOCK)
    source.feed(first)
    assert not deep.is_started.wait(0.1)  # held, with a tenth standing by
    for _ in range(4):
        source.feed(first)
    assert deep.is_started.wait(10)  # started once half a second did
    _hang_up(utterance, source, player)


def test_the_cushion_is_read_from_the_configuration_when_none_is_given(sd, monkeypatch):
    """Left unset, the player takes the configured cushion rather than a
    constant of its own, so the setting reaches the device that plays."""
    monkeypatch.setattr(CFG, "LLM_SPEECH_PLAYER_PREBUFFER_SECONDS", 0.5)
    sd.OutputStream = TimedStream

    utterance = PcmUtterance(SpeechAudio(RATE, _pausing_source()))
    started = time.monotonic()
    utterance.play(timeout=15)

    [stream] = FakeOutputStream.instances
    assert stream.started_at - started >= STALL_SECONDS / 2


def test_a_zero_cushion_still_waits_for_the_first_audio(sd):
    """`0` starts on whatever has arrived, which is not the same as starting on
    nothing: a device fed an empty first block opens the sentence on silence."""

    def arrives_late():
        time.sleep(0.2)
        yield _pcm([5] * 1600)
        yield _pcm([5] * 1600)

    sd.OutputStream = TimedStream
    utterance = PcmUtterance(SpeechAudio(RATE, arrives_late()), prebuffer_seconds=0.0)
    started = time.monotonic()
    utterance.play(timeout=5)

    [stream] = FakeOutputStream.instances
    assert stream.started_at - started >= 0.15  # waited for the first chunk
    assert _played(stream)[:1600].tolist() == [5] * 1600  # not silence


def test_the_newest_speech_setting_is_the_last_field():
    """A dataclass is positional too: a field added in the middle rebinds every
    field after it for a caller that passes them that way."""
    assert [field.name for field in fields(SpeechConfig)][-1] == (
        "player_prebuffer_seconds"
    )


def test_the_cushion_is_added_last_so_a_positional_caller_still_fits(sd):
    """An older call passing the older options by position keeps meaning what
    it meant: the cushion sits after them, not among them."""
    events = []
    utterance = PcmUtterance(
        SpeechAudio(RATE, [_pcm([5] * 1600)]),
        BLOCK,  # block_frames
        32,  # read_ahead
        lambda: ProgramUtterance(events),  # fallback, the fourth positional
    )
    sd.OutputStream = GoneOutputStream  # a device that cannot play

    utterance.play(timeout=2)

    assert events == ["played", "cleaned"]


def test_the_read_ahead_count_does_not_cap_the_cushion(sd):
    """A cushion counted in seconds cannot be bounded by a count of chunks: a
    backend streaming small ones would never hold it, so the sentence would
    start under its cushion once the wait ran out."""
    sd.OutputStream = ManualStream

    utterance, source, player, stream = _start_playing(
        0.4, block_frames=BLOCK, read_ahead=2
    )
    # Forty chunks of ten milliseconds are what the cushion asks for. A reader
    # capped at two would stop taking them, and `feed` would find them unread.
    for _ in range(40):
        source.feed(_pcm([5] * 160))

    assert stream.is_started.wait(10)
    _hang_up(utterance, source, player)


def test_a_longer_cushion_absorbs_a_stall_in_the_audio(sd):
    """A stall mid-sentence is what the listener hears as a clipped word; the
    cushion is what decides whether it is heard at all.

    Time is counted in blocks the test plays, never in seconds: the source
    produces one block per block played, then goes quiet for the stall."""
    sd.OutputStream = ManualStream
    stall_blocks = math.ceil(STALL_SECONDS / BLOCK_SECONDS)

    def underruns_with(prebuffer_seconds):
        utterance, source, player, stream = _start_playing(
            prebuffer_seconds, block_frames=BLOCK
        )
        # The device starts once the cushion stands by, and not before.
        for _ in range(math.ceil(prebuffer_seconds * RATE / BLOCK)):
            source.feed(_pcm([5] * BLOCK))
        assert stream.is_started.wait(10)
        for _ in range(5):  # production keeps pace with playing
            stream.tick()
            source.feed(_pcm([5] * BLOCK))
        for _ in range(stall_blocks):  # the engine stalls; the device does not
            stream.tick()
        for _ in range(3):  # and recovers
            source.feed(_pcm([5] * BLOCK))
            stream.tick()
        heard = utterance.underruns
        _hang_up(utterance, source, player)
        return heard

    thin = underruns_with(0.1)  # the hardcoded tenth the cushion replaced
    deep = underruns_with(0.5)  # the default the cushion now asks for

    assert thin >= 1  # the stall was heard on the old cushion
    assert deep == 0  # and absorbed on the new one
