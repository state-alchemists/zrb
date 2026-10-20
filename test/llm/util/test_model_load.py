"""One heavy local model loads at a time (ADR-0115).

The spike of one load on a small machine is survivable; two of them peaking
together is what the kernel's OOM killer picks the chat for.
"""

import threading
import time

import pytest

from zrb.llm.util import model_load
from zrb.llm.util.model_load import heavy_model_load


def test_two_loads_never_run_at_once():
    first_inside = threading.Event()
    second_inside = threading.Event()
    release_first = threading.Event()

    def first():
        with heavy_model_load("the first model"):
            first_inside.set()
            release_first.wait(5)

    def second():
        with heavy_model_load("the second model"):
            second_inside.set()

    first_thread = threading.Thread(target=first)
    first_thread.start()
    assert first_inside.wait(5)
    second_thread = threading.Thread(target=second)
    second_thread.start()

    # The second waits for the first, and says so by staying outside.
    assert not second_inside.wait(0.2)
    release_first.set()
    first_thread.join(5)
    second_thread.join(5)
    assert second_inside.is_set()


def test_a_wedged_load_does_not_hold_the_next_one_forever(monkeypatch):
    """A load that never returns (a hung download) must not cost the other
    feature its model for the rest of the session."""
    monkeypatch.setattr(model_load, "WAIT_SECONDS", 0.05)
    wedged_inside = threading.Event()
    release_wedged = threading.Event()
    next_inside = threading.Event()

    def wedged():
        with heavy_model_load("the wedged model"):
            wedged_inside.set()
            release_wedged.wait(5)

    def next_load():
        with heavy_model_load("the model behind it"):
            next_inside.set()

    wedged_thread = threading.Thread(target=wedged)
    wedged_thread.start()
    assert wedged_inside.wait(5)
    started = time.monotonic()
    next_load()
    try:
        assert next_inside.is_set()  # it went ahead
        assert time.monotonic() - started < 2.0  # after waiting, not blocking
    finally:
        release_wedged.set()
        wedged_thread.join(5)


def test_the_slot_is_released_when_the_load_fails():
    with pytest.raises(RuntimeError):
        with heavy_model_load("the failing model"):
            raise RuntimeError("no model")

    # Nothing is left held: this returns at once.
    with heavy_model_load("the model after it"):
        pass
