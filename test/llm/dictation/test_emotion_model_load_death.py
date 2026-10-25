"""A tone child that dies while it loads its model: a death, counted against
`MAX_DEATHS`, unlike a model the child reports it cannot load (ADR-0115)."""

import threading

import pytest

from zrb.llm.dictation import emotion_model
from zrb.llm.dictation.emotion_model import ChildDiedError, EmotionWorker

from .test_emotion_model import STARTED, _classify, in_threads  # noqa: F401


def test_a_child_silent_while_loading_is_a_death(in_threads):  # noqa: F811
    """The thread standing in for the child never answers, as a child the OOM
    killer took mid-load never does."""
    release = threading.Event()

    def wedged(repo):
        # A real child dies when it is terminated; a thread cannot, so it watches
        # for the terminate the worker sends instead of sitting out the join.
        while not release.wait(0.01):
            if any(process.was_terminated for process in STARTED):
                break
        return _classify

    in_threads.setattr(emotion_model, "load_classifier", wedged)
    in_threads.setattr(emotion_model, "READY_TIMEOUT_SECONDS", 0.1)
    in_threads.setattr(emotion_model, "MAX_DEATHS", 1)
    in_threads.setattr(emotion_model, "STOP_GRACE_SECONDS", 0.1)
    worker = EmotionWorker("me/e2v")
    try:
        with pytest.raises(ChildDiedError, match="said nothing"):
            worker.start()
        with pytest.raises(RuntimeError, match="no room for it"):
            worker.start()
    finally:
        release.set()
        worker.close()


def test_a_model_the_child_cannot_load_is_not_a_death(in_threads):  # noqa: F811
    """The child answered: the model will not load however often it is asked,
    which says nothing about the machine's room for it."""

    def broken(repo):
        raise ImportError("no funasr here")

    in_threads.setattr(emotion_model, "load_classifier", broken)
    in_threads.setattr(emotion_model, "MAX_DEATHS", 1)
    worker = EmotionWorker("me/e2v")
    try:
        for _ in range(2):
            with pytest.raises(RuntimeError, match="no funasr here") as raised:
                worker.start()
            assert not isinstance(raised.value, ChildDiedError)
    finally:
        worker.close()
