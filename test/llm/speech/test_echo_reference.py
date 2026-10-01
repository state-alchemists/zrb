import time

import pytest

from zrb.llm.speech.echo_reference import RATE, EchoReference

np = pytest.importorskip("numpy")


def test_what_was_written_is_read_back_at_its_time():
    reference = EchoReference(origin=100.0)
    reference.write(100.5, np.arange(1, 5, dtype=np.float32))

    out = reference.read(100.5 - 2 / RATE, 8)

    assert out.tolist() == [0, 0, 1, 2, 3, 4, 0, 0]


def test_a_gap_between_writes_reads_as_silence_not_old_audio():
    reference = EchoReference(seconds=0.001)  # a 16-sample ring
    reference.write(0.0, np.ones(16, np.float32))
    reference.write(32 / RATE, np.full(4, 2.0, np.float32))

    assert reference.read(16 / RATE, 16).tolist() == [0.0] * 16
    assert reference.read(32 / RATE, 4).tolist() == [2.0] * 4
    # Overwritten by the ring wrapping round: gone.
    assert reference.read(0.0, 4).tolist() == [0.0] * 4


def test_a_write_longer_than_the_ring_keeps_its_end():
    reference = EchoReference(seconds=0.0005)  # 8 samples
    reference.write(0.0, np.arange(20, dtype=np.float32))
    assert reference.read(12 / RATE, 8).tolist() == list(range(12, 20))


def test_nothing_written_reads_as_silence():
    assert EchoReference().read(1.0, 3).tolist() == [0.0, 0.0, 0.0]


def test_is_active_counts_players():
    reference = EchoReference()
    reference.add_player(+1)
    reference.add_player(+1)
    reference.add_player(-1)
    assert reference.is_active
    reference.add_player(-1)
    reference.add_player(-1)  # never below zero
    assert not reference.is_active


def test_a_write_long_after_the_last_clears_the_ring_without_filling_the_gap():
    reference = EchoReference(origin=0.0)
    reference.write(1.0, np.ones(4, np.float32))
    started = time.perf_counter()
    reference.write(1_000_000.0, np.full(4, 2.0, np.float32))  # hours later
    assert time.perf_counter() - started < 0.5
    assert reference.read(1.0, 4).tolist() == [0.0] * 4
    assert reference.read(1_000_000.0, 4).tolist() == [2.0] * 4
