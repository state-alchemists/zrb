"""`EchoCancellation`: measuring the echo delay from the audio and feeding
the canceller the reference lined up with each microphone block."""

import pytest

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.echo import EchoCancellation, NoEchoCanceller, get_echo_canceller
from zrb.llm.dictation.echo.any_echo_canceller import AnyEchoCanceller
from zrb.llm.dictation.echo.numpy_canceller import NumpyEchoCanceller
from zrb.llm.speech.echo_reference import EchoReference

np = pytest.importorskip("numpy")
RATE = 16000
BLOCK = 1600


def _played(seconds, seed=0):
    rng = np.random.default_rng(seed)
    x = np.convolve(rng.normal(0, 1, int(RATE * seconds)), np.ones(3) / 3, "same")
    return (0.1 * x).astype(np.float32)


class RecordingCanceller(AnyEchoCanceller):
    """Passes the microphone through and records what it was given."""

    def __init__(self, converged=True):
        self.fars: list = []
        self.resets = 0
        self._converged = converged

    @property
    def is_converged(self):
        return self._converged

    def reset(self):
        self.resets += 1

    def process(self, mic, far):
        self.fars.append(far.copy())
        return mic


def _feed(cancellation, mic, start, blocks=None):
    out = []
    for i in range(0, len(mic) - BLOCK + 1, BLOCK):
        out.append(cancellation.process(mic[i : i + BLOCK], start + i / RATE))
    return np.concatenate(out)


def _setup(delay_s, seconds=6, noise=0.001, clock_offset=0.0):
    """zrb plays from t=10 s; the microphone hears it *delay_s* later, and
    stamps its blocks *clock_offset* late (a wrong reported latency)."""
    far = _played(seconds)
    reference = EchoReference(origin=0.0, seconds=30)
    reference.write(10.0, far)
    d = int(RATE * delay_s)
    mic = np.concatenate([np.zeros(d), 0.5 * far])[: len(far)].astype(np.float32)
    mic += np.random.default_rng(9).normal(0, noise, len(mic)).astype(np.float32)
    return reference, far, mic, 10.0 + clock_offset


@pytest.mark.parametrize("delay, offset", [(0.049, 0.0), (0.049, 0.6), (0.2, -0.3)])
def test_the_delay_is_measured_from_the_audio_whatever_the_clocks_say(delay, offset):
    reference, far, mic, start = _setup(delay, clock_offset=offset)
    cancellation = EchoCancellation(RecordingCanceller(), reference)

    _feed(cancellation, mic, start)

    assert cancellation.delay == pytest.approx(delay + offset, abs=0.002)


def test_the_reference_handed_over_leads_the_echo():
    reference, far, mic, start = _setup(0.05)
    canceller = RecordingCanceller()
    cancellation = EchoCancellation(canceller, reference)
    _feed(cancellation, mic, start)

    # The last block: the reference given leads the echo by 40 ms.
    last_mic = mic[-BLOCK - (len(mic) % BLOCK) :][:BLOCK]
    given = canceller.fars[-1]
    lead = int(RATE * 0.04)
    # given[k] is what was played 40 ms before mic[k + 40 ms] heard it.
    assert np.allclose(0.5 * given[:-lead], last_mic[lead:], atol=0.01)


def test_until_the_delay_is_known_it_is_not_ready_and_gets_silence():
    reference, far, mic, start = _setup(0.05)
    canceller = RecordingCanceller()
    cancellation = EchoCancellation(canceller, reference)

    cancellation.process(mic[:BLOCK], start)

    assert not cancellation.is_ready and cancellation.delay is None
    assert not canceller.fars[0].any()


def test_with_nothing_played_no_delay_is_guessed():
    reference = EchoReference(origin=0.0)
    cancellation = EchoCancellation(RecordingCanceller(), reference)
    noise = np.random.default_rng(1).normal(0, 0.01, RATE * 4).astype(np.float32)
    _feed(cancellation, noise, 10.0)
    assert cancellation.delay is None


def test_audio_unrelated_to_what_was_played_gives_no_delay():
    reference, far, _, start = _setup(0.05)
    unrelated = _played(6, seed=42)
    cancellation = EchoCancellation(RecordingCanceller(), reference)
    _feed(cancellation, unrelated, start)
    assert cancellation.delay is None


def test_a_delay_that_moves_starts_the_canceller_over():
    canceller = RecordingCanceller()
    reference, far, mic, start = _setup(0.05, seconds=6)
    cancellation = EchoCancellation(canceller, reference)
    _feed(cancellation, mic, start)
    assert cancellation.delay == pytest.approx(0.05, abs=0.002)

    # Another output device: the same audio now arrives 150 ms later.
    reference.write(20.0, far)
    later = np.concatenate([np.zeros(int(RATE * 0.2)), 0.5 * far])[: len(far)].astype(
        np.float32
    )
    _feed(cancellation, later, 20.0)

    assert cancellation.delay == pytest.approx(0.2, abs=0.002)
    assert canceller.resets == 1


def test_a_new_echo_path_must_prove_itself_quiet_again():
    canceller = QuietCanceller(leftover=0.001)
    reference, far, mic, start = _setup(0.05, seconds=6)
    cancellation = EchoCancellation(canceller, reference)
    _feed(cancellation, mic, start)
    assert cancellation.is_ready

    reference.write(20.0, far)
    later = np.concatenate([np.zeros(int(RATE * 0.2)), 0.5 * far])[: len(far)]
    canceller.leftover = 0.05
    _feed(cancellation, later.astype(np.float32), 20.0)

    assert cancellation.delay == pytest.approx(0.2, abs=0.002)
    assert not cancellation.is_ready


class QuietCanceller(RecordingCanceller):
    """Cancels perfectly: leaves only what *leftover* says."""

    def __init__(self, leftover=0.0, converged=True):
        super().__init__(converged)
        self.leftover = leftover

    def process(self, mic, far):
        super().process(mic, far)
        return np.full(len(mic), self.leftover, np.float32)


def test_it_is_ready_once_what_is_left_of_zrb_is_quiet():
    reference, far, mic, start = _setup(0.05)
    cancellation = EchoCancellation(QuietCanceller(leftover=0.001), reference)
    _feed(cancellation, mic, start)
    assert cancellation.is_ready


def test_it_is_not_ready_while_what_is_left_is_loud_enough_to_start_speech():
    reference, far, mic, start = _setup(0.05)
    cancellation = EchoCancellation(QuietCanceller(leftover=0.05), reference)
    _feed(cancellation, mic, start)
    assert cancellation.delay is not None and not cancellation.is_ready


def test_it_is_not_ready_until_the_canceller_has_converged():
    reference, far, mic, start = _setup(0.05)
    canceller = QuietCanceller(leftover=0.001, converged=False)
    cancellation = EchoCancellation(canceller, reference)
    _feed(cancellation, mic, start)
    assert cancellation.delay is not None and not cancellation.is_ready


def test_once_ready_it_stays_ready_while_the_user_talks_over_zrb():
    reference, far, mic, start = _setup(0.05)
    canceller = QuietCanceller(leftover=0.001)
    cancellation = EchoCancellation(canceller, reference)
    _feed(cancellation, mic, start)
    assert cancellation.is_ready

    canceller.leftover = 0.2  # the user, loud on purpose
    _feed(cancellation, mic[: RATE * 2], start + 6)
    assert cancellation.is_ready


def test_the_threshold_is_the_level_that_starts_an_utterance():
    reference, far, mic, start = _setup(0.05)
    cancellation = EchoCancellation(
        QuietCanceller(leftover=0.02), reference, DictationConfig(threshold=0.05)
    )
    _feed(cancellation, mic, start)
    assert cancellation.is_ready


def test_the_numpy_canceller_removes_the_echo_once_lined_up():
    reference, far, mic, start = _setup(0.08, seconds=10, clock_offset=0.3)
    cancellation = EchoCancellation(NumpyEchoCanceller(), reference)
    out = _feed(cancellation, mic, start)
    tail = slice(RATE * 6, len(out))
    removed = 10 * np.log10(np.sum(mic[tail] ** 2) / np.sum(out[tail] ** 2))
    assert removed > 15
    assert cancellation.is_ready


def test_no_canceller_needs_no_reference_and_is_always_ready():
    cancellation = EchoCancellation(NoEchoCanceller(), EchoReference())
    block = np.ones(BLOCK, np.float32)
    assert cancellation.is_ready
    assert cancellation.process(block, 1.0) is block or np.array_equal(
        cancellation.process(block, 1.0), block
    )
    assert cancellation.canceller.name == "none"
    assert not cancellation.canceller.needs_reference


def test_builtin_cancellers_by_name():
    assert get_echo_canceller("numpy").name == "numpy"
    assert get_echo_canceller("").name == "numpy"
    assert get_echo_canceller("NONE").name == "none"
    own = RecordingCanceller()
    assert get_echo_canceller(own) is own
    with pytest.raises(ValueError, match="unknown echo canceller"):
        get_echo_canceller("webrtc")


def test_the_lead_is_configured():
    reference, far, mic, start = _setup(0.05)
    canceller = RecordingCanceller()
    cancellation = EchoCancellation(
        canceller, reference, DictationConfig(echo_lead=0.1)
    )
    _feed(cancellation, mic, start)

    last_mic = mic[-BLOCK - (len(mic) % BLOCK) :][:BLOCK]
    lead = int(RATE * 0.1)
    assert np.allclose(0.5 * canceller.fars[-1][:-lead], last_mic[lead:], atol=0.01)


def test_a_delay_outside_the_configured_search_is_not_found():
    reference, far, mic, start = _setup(0.2)
    config = DictationConfig(echo_min_delay=0.0, echo_max_delay=0.1)
    cancellation = EchoCancellation(RecordingCanceller(), reference, config)
    _feed(cancellation, mic, start)
    assert cancellation.delay is None


def test_readiness_judges_the_configured_number_of_blocks():
    canceller = QuietCanceller(leftover=0.001)
    reference, far, mic, start = _setup(0.05, seconds=6)
    config = DictationConfig(echo_ready_blocks=1000)
    cancellation = EchoCancellation(canceller, reference, config)
    _feed(cancellation, mic, start)
    # Six seconds hold far fewer than a thousand blocks of zrb speaking.
    assert not cancellation.is_ready


def test_the_reference_keeps_enough_audio_for_the_widest_search():
    reference = EchoReference(origin=0.0, seconds=1)
    config = DictationConfig(echo_delay_window=3, echo_min_delay=-1, echo_max_delay=2)
    EchoCancellation(RecordingCanceller(), reference, config)
    assert reference.seconds >= 3 + 2 + 1
