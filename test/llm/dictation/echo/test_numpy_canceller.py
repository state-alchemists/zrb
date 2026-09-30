"""`NumpyEchoCanceller` on a synthetic echo: a delayed, filtered copy of what
zrb played, plus microphone noise."""

import pytest

from zrb.llm.dictation.echo.numpy_canceller import NumpyEchoCanceller

np = pytest.importorskip("numpy")
RATE = 16000


def _speechlike(seconds, seed=0):
    """Noise shaped and switched on and off like speech, with silences."""
    rng = np.random.default_rng(seed)
    x = np.convolve(rng.normal(0, 1, int(RATE * seconds)), np.ones(4) / 4, "same")
    gate = (np.sin(np.arange(len(x)) / RATE * 2 * np.pi * 0.7) > -0.3).astype(float)
    return (0.1 * x * gate).astype(np.float32)


def _echo(far, delay=0.03, seed=1):
    rng = np.random.default_rng(seed)
    path = np.zeros(int(RATE * 0.1))
    path[int(RATE * delay)] = 0.6
    path += rng.normal(0, 0.02, len(path)) * np.exp(-np.arange(len(path)) / 300)
    return np.convolve(far, path)[: len(far)].astype(np.float32)


def _run(canceller, mic, far, chunk=1600):
    return np.concatenate(
        [
            canceller.process(mic[i : i + chunk], far[i : i + chunk])
            for i in range(0, len(mic), chunk)
        ]
    )


def _db(before, after):
    return 10 * np.log10(np.sum(before**2) / (np.sum(after**2) + 1e-12))


def test_it_learns_the_echo_and_removes_it():
    far = _speechlike(12)
    mic = _echo(far) + np.random.default_rng(2).normal(0, 0.0005, len(far)).astype(
        np.float32
    )
    silence = np.zeros(RATE // 2, np.float32)  # lets it measure the noise
    canceller = NumpyEchoCanceller()
    _run(
        canceller,
        silence
        + np.random.default_rng(3).normal(0, 0.0005, len(silence)).astype(np.float32),
        silence,
    )
    assert not canceller.is_converged

    out = _run(canceller, mic, far)

    assert canceller.is_converged
    tail = slice(RATE * 6, None)
    assert _db(mic[tail], out[tail]) > 20


def test_output_is_as_long_as_input_whatever_the_chunks():
    canceller = NumpyEchoCanceller()
    for size in (1, 159, 160, 1600, 7):
        chunk = np.zeros(size, np.float32)
        assert len(canceller.process(chunk, chunk)) == size


def test_with_nothing_played_the_microphone_passes_through():
    canceller = NumpyEchoCanceller(suppress=False)
    mic = np.random.default_rng(4).normal(0, 0.01, RATE).astype(np.float32)
    out = _run(canceller, mic, np.zeros(RATE, np.float32), chunk=160)
    assert np.allclose(out, mic, atol=1e-6)


def test_it_converges_after_a_couple_of_seconds_of_zrb_speaking():
    far = _speechlike(1.5)
    canceller = NumpyEchoCanceller()
    _run(canceller, _echo(far), far)
    assert not canceller.is_converged
    more = _speechlike(2, seed=7)
    _run(canceller, _echo(more), more)
    assert canceller.is_converged


def test_reset_forgets_what_it_learned():
    far = _speechlike(8)
    mic = _echo(far)
    canceller = NumpyEchoCanceller()
    _run(
        canceller,
        np.zeros(RATE // 2, np.float32) + 1e-4,
        np.zeros(RATE // 2, np.float32),
    )
    _run(canceller, mic, far)
    assert canceller.is_converged

    canceller.reset()

    assert not canceller.is_converged
    assert canceller.name == "numpy"
