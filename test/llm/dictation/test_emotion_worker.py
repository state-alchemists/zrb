"""The tone's model in a child process: one worker per detector, the deaths it
is allowed, a session ending mid-load, and a worker that cannot start
(ADR-0115)."""

import asyncio
import threading
import time

import pytest

from zrb.llm.dictation.emotion import EmotionDetector, Tone

from .test_emotion import LABELS, _wait_until


@pytest.mark.asyncio
async def test_out_of_process_classifies_through_a_worker(monkeypatch):
    workers: list[FakeWorker] = []

    class FakeWorker:
        def __init__(self, repo):
            self.repo = repo
            self.closed = False
            self.is_started = False
            workers.append(self)

        def start(self):
            self.is_started = True
            return lambda samples: {
                "labels": LABELS,
                "scores": [0.0, 0.9, 0.1, 0.0, 0.0],
            }

        def close(self):
            self.closed = True
            self.is_started = False

    monkeypatch.setattr("zrb.llm.dictation.emotion.EmotionWorker", FakeWorker)
    detector = EmotionDetector("me/e2v", out_of_process=True)

    assert await detector.hear(b"\x00\x10" * 160) == Tone("happy", 0.9)
    detector.close()

    [worker] = workers
    assert worker.repo == "me/e2v"
    assert worker.closed


@pytest.mark.asyncio
async def test_a_worker_whose_child_died_is_started_again_beside_the_turn(
    monkeypatch,
):
    """One dead child costs the tones it would have heard, not every tone after
    it: the next clip starts another child through the same worker, which is
    what counts the deaths against `MAX_DEATHS`. That clip does not wait for the
    restart, which is a whole model load: the turn waits for its tone
    (ADR-0115)."""
    restarting = threading.Event()
    release = threading.Event()
    workers: list[DyingWorker] = []

    class DyingWorker:
        def __init__(self, repo):
            self.closed = False
            self.is_started = False
            self.starts = 0
            self.clips = 0
            workers.append(self)

        def start(self):
            self.starts += 1
            if self.starts > 1:
                restarting.set()
                release.wait(5)
            self.is_started = True
            return self._classify

        def _classify(self, samples):
            self.clips += 1
            if self.clips == 1:
                # The kernel picked this child, as `make_expendable` asked it to.
                self.is_started = False
                raise RuntimeError("the emotion worker stopped (killed)")
            return {"labels": LABELS, "scores": [0.0, 0.9, 0.1, 0.0, 0.0]}

        def close(self):
            self.closed = True
            self.is_started = False

    monkeypatch.setattr("zrb.llm.dictation.emotion.EmotionWorker", DyingWorker)
    detector = EmotionDetector("me/e2v", out_of_process=True)
    clip = b"\x00\x10" * 160

    assert await detector.hear(clip) is None
    assert await asyncio.wait_for(detector.hear(clip), timeout=2) is None
    assert await asyncio.to_thread(restarting.wait, 5)
    release.set()

    assert await _keep_hearing(detector, clip, lambda tone: tone is not None) == (
        Tone("happy", 0.9)
    )
    [worker] = workers
    assert worker.starts == 2
    detector.close()


@pytest.mark.asyncio
async def test_a_detector_gives_up_after_the_deaths_it_is_allowed(monkeypatch):
    """`MAX_DEATHS` counts children, not worker objects. A detector that made a
    new worker per attempt would give a machine that cannot hold the model a
    fresh child after every kill, and reload 1 GB each time."""
    workers: list[DoomedWorker] = []

    class DoomedWorker:
        def __init__(self, repo):
            self.deaths = 0
            self.is_started = False
            workers.append(self)

        def start(self):
            if self.deaths >= 2:  # what `EmotionWorker.start` raises at the limit
                raise RuntimeError("this machine has no room for it")
            self.is_started = True
            return self._classify

        def _classify(self, samples):
            self.is_started = False
            self.deaths += 1
            raise RuntimeError("the emotion worker stopped (killed)")

        def close(self):
            self.is_started = False

    monkeypatch.setattr("zrb.llm.dictation.emotion.EmotionWorker", DoomedWorker)
    detector = EmotionDetector("me/e2v", out_of_process=True)

    assert (
        await _keep_hearing(
            detector, b"\x00\x10" * 160, lambda _: bool(detector.unavailable_reason)
        )
        is None
    )
    [worker] = workers
    assert worker.deaths == 2  # the third attempt found the budget spent
    assert "no room for it" in detector.unavailable_reason


async def _keep_hearing(detector, clip, until, timeout: float = 2.0):
    """Hear *clip* as utterances keep arriving, until *until* holds for the
    tone heard, and return that tone."""
    deadline = time.monotonic() + timeout
    while True:
        tone = await detector.hear(clip)
        if until(tone) or time.monotonic() > deadline:
            return tone
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_a_session_ending_mid_load_closes_the_worker_it_made(monkeypatch):
    """The model loads on a thread of its own, so a session can end before it
    lands. The child it made is then closed instead of kept: nothing can reach
    it, and it would hold its share of the machine for the rest of the chat."""
    started = threading.Event()
    release = threading.Event()
    workers: list[LoadingWorker] = []

    class LoadingWorker:
        def __init__(self, repo):
            self.closed = False
            self.is_started = False
            workers.append(self)

        def start(self):
            started.set()
            release.wait(5)
            self.is_started = True
            return lambda samples: {
                "labels": LABELS,
                "scores": [0.0, 0.9, 0.1, 0.0, 0.0],
            }

        def close(self):
            self.closed = True
            self.is_started = False

    monkeypatch.setattr("zrb.llm.dictation.emotion.EmotionWorker", LoadingWorker)
    detector = EmotionDetector("me/e2v", out_of_process=True)
    prepare = asyncio.create_task(detector.prepare(lambda message: None))
    assert await asyncio.to_thread(started.wait, 5)

    prepare.cancel()  # what `_close_emotion` does to a load still running
    detector.close()
    # The worker was kept before its model loaded, so closing reaches it now
    # rather than when the load lands.
    assert workers[0].closed
    release.set()

    assert await _wait_until(lambda: bool(workers) and workers[0].closed)
    assert await detector.hear(b"\x00\x10" * 160) is None
    assert len(workers) == 1


@pytest.mark.asyncio
async def test_a_worker_that_cannot_start_costs_only_the_tone(monkeypatch, caplog):
    class DeadWorker:
        def __init__(self, repo):
            self.closed = False

        def start(self):
            raise RuntimeError("this machine has no room for it")

        def close(self):
            self.closed = True

    monkeypatch.setattr("zrb.llm.dictation.emotion.EmotionWorker", DeadWorker)
    detector = EmotionDetector(out_of_process=True)

    assert await detector.hear(b"\x00\x00") is None
    assert "no room for it" in detector.unavailable_reason
    assert "this machine has no room for it" in caplog.text
