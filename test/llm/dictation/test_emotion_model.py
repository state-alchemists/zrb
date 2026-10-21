"""emotion2vec+ in a child process: the model's load spike lands there (ADR-0115).

The child is a real process in production and a thread here, so what these
cover is the protocol — start, ready, classify, a child that died — without
loading a two-gigabyte model into a test.
"""

import multiprocessing
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from zrb.llm.dictation import emotion_model
from zrb.llm.dictation.emotion_model import EmotionWorker

LABELS = ["happy", "sad"]
SCORES = [0.9, 0.1]


class ThreadProcess:
    """A `multiprocessing.Process` that runs its target as a thread."""

    def __init__(self, target, args, daemon):
        self._target = target
        self._args = args
        self._thread = None
        self.was_terminated = False

    def start(self):
        self._thread = threading.Thread(target=self._target, args=self._args)
        self._thread.daemon = True
        self._thread.start()

    def join(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()

    def terminate(self):
        self.was_terminated = True


class ChildEnd:
    """The child's end of the pipe as `_spawn_child` sees it: an object it
    closes right after starting the child, holding the end the thread uses.

    A real spawn can close that end, because the child has a handle of its own.
    A thread shares the parent's, and the only portable way to give it a handle
    of its own would be a platform-specific duplication (`os.dup` is a file
    descriptor call; on Windows this holds a Win32 handle). So the close is a
    no-op here and the thread keeps the real end."""

    def __init__(self, connection):
        self.connection = connection

    def close(self):
        pass


class ThreadContext:
    """A `multiprocessing` context whose processes are threads."""

    def Pipe(self, duplex=True):
        parent_connection, child_connection = multiprocessing.Pipe(duplex)
        return parent_connection, ChildEnd(child_connection)

    def Process(self, target, args, daemon):
        child_end, *rest = args
        process = ThreadProcess(target, (child_end.connection, *rest), daemon)
        STARTED.append(process)
        return process


#: Every thread standing in for a child, in the order they were started.
STARTED: list[ThreadProcess] = []


def _classify(samples):
    return {"labels": LABELS, "scores": SCORES}


def _fails_on_bad(samples):
    """A model that reads `b"bad"` and nothing else wrong: a per-clip failure."""
    if samples == b"bad":
        raise ValueError("bad clip")
    return _classify(samples)


@pytest.fixture
def in_threads(monkeypatch):
    """`EmotionWorker` starts a thread instead of a process, with a fake model."""
    STARTED.clear()
    monkeypatch.setattr(
        emotion_model,
        "multiprocessing",
        SimpleNamespace(get_context=lambda method: ThreadContext()),
    )
    monkeypatch.setattr(emotion_model, "make_expendable", lambda: None)
    monkeypatch.setattr(emotion_model, "load_classifier", lambda repo: _classify)
    return monkeypatch


def test_the_worker_classifies_through_its_child(in_threads):
    worker = EmotionWorker("me/e2v")
    try:
        classify = worker.start()
        assert worker.is_started
        assert classify(b"\x00\x00") == {"labels": LABELS, "scores": SCORES}
    finally:
        worker.close()
    assert not worker.is_started


def test_a_started_worker_hands_out_the_same_child_again(in_threads):
    worker = EmotionWorker("me/e2v")
    try:
        assert worker.start() == worker.start()
    finally:
        worker.close()


def test_a_model_that_will_not_load_says_why(in_threads):
    def broken(repo):
        raise ImportError("no funasr here")

    in_threads.setattr(emotion_model, "load_classifier", broken)
    worker = EmotionWorker("me/e2v")

    with pytest.raises(RuntimeError, match="no funasr here"):
        worker.start()
    assert not worker.is_started


@pytest.mark.filterwarnings(
    "ignore::pytest.PytestUnhandledThreadExceptionWarning"
)
def test_a_child_that_died_is_forgotten_and_the_next_one_starts(in_threads):
    attempts = []

    def die_once(repo):
        attempts.append(repo)
        if len(attempts) == 1:

            def dies(samples):
                raise SystemExit("killed")

            return dies
        return _classify

    in_threads.setattr(emotion_model, "load_classifier", die_once)
    worker = EmotionWorker("me/e2v")
    try:
        with pytest.raises(RuntimeError, match="stopped"):
            worker.start()(b"\x00\x00")
        assert worker.start()(b"\x00\x00") == {"labels": LABELS, "scores": SCORES}
    finally:
        worker.close()
    assert len(attempts) == 2


@pytest.mark.filterwarnings(
    "ignore::pytest.PytestUnhandledThreadExceptionWarning"
)
def test_a_child_that_keeps_dying_is_given_up_on(in_threads):
    def dies(samples):
        raise SystemExit("killed")

    in_threads.setattr(emotion_model, "load_classifier", lambda repo: dies)
    in_threads.setattr(emotion_model, "MAX_DEATHS", 1)
    worker = EmotionWorker("me/e2v")
    try:
        with pytest.raises(RuntimeError, match="stopped"):
            worker.start()(b"\x00\x00")
        with pytest.raises(RuntimeError, match="no room for it"):
            worker.start()
    finally:
        worker.close()


def test_a_clip_that_gets_no_answer_stops_the_child(in_threads):
    """A child that says nothing for a clip is wedged, not slow. It is stopped
    like a dead one, so later clips do not each wait out the timeout, and its
    model does not stay resident for a worker nothing can use."""
    attempts = []

    def wedged_once(repo):
        attempts.append(repo)
        if len(attempts) == 1:

            def wedged(samples):
                threading.Event().wait(0.3)
                return {"labels": LABELS, "scores": SCORES}

            return wedged
        return _classify

    in_threads.setattr(emotion_model, "load_classifier", wedged_once)
    in_threads.setattr(emotion_model, "CLASSIFY_TIMEOUT_SECONDS", 0.05)
    worker = EmotionWorker("me/e2v")
    try:
        with pytest.raises(RuntimeError, match="said nothing"):
            worker.start()(b"\x00\x00")
        assert not worker.is_started
        assert worker.start()(b"\x00\x00") == {"labels": LABELS, "scores": SCORES}
    finally:
        worker.close()
    assert len(attempts) == 2


def test_one_clip_the_child_cannot_classify_keeps_the_child(in_threads):
    """A clip the model cannot read is the clip's problem: the next clip is
    other audio, and the child that can read it is already loaded."""
    in_threads.setattr(emotion_model, "load_classifier", lambda repo: _fails_on_bad)
    worker = EmotionWorker("me/e2v")
    try:
        classify = worker.start()
        with pytest.raises(RuntimeError, match="bad clip"):
            classify(b"bad")
        assert worker.is_started
        assert classify(b"\x00\x00") == {"labels": LABELS, "scores": SCORES}
    finally:
        worker.close()
    assert len(STARTED) == 1


def test_a_child_that_cannot_classify_any_clip_is_restarted(in_threads):
    """The second clip in a row failing is the worker's problem, not the
    clip's: the child is forgotten like a dead one, so the next clip starts
    another instead of asking the same broken model for the rest of the
    session."""
    in_threads.setattr(emotion_model, "load_classifier", lambda repo: _fails_on_bad)
    worker = EmotionWorker("me/e2v")
    try:
        classify = worker.start()
        for _ in range(2):
            with pytest.raises(RuntimeError, match="bad clip"):
                classify(b"bad")
        assert not worker.is_started
        assert len(STARTED) == 1
        assert not STARTED[0].is_alive()  # the broken child is gone

        worker.start()
        assert len(STARTED) == 2
    finally:
        worker.close()


def test_a_clip_the_child_reads_clears_the_count(in_threads):
    """The count is of clips failing in a row: a clip the child reads ends it,
    so a rare bad one never adds up to a reload of the model."""
    in_threads.setattr(emotion_model, "load_classifier", lambda repo: _fails_on_bad)
    worker = EmotionWorker("me/e2v")
    try:
        classify = worker.start()
        for samples in (b"bad", b"\x00\x00", b"bad"):
            if samples == b"bad":
                with pytest.raises(RuntimeError, match="bad clip"):
                    classify(samples)
            else:
                assert classify(samples) == {"labels": LABELS, "scores": SCORES}
        assert worker.is_started
    finally:
        worker.close()
    assert len(STARTED) == 1


def test_a_close_while_the_model_loads_stops_the_child(in_threads):
    """`start` waits for the model; `close` must not wait for `start`.

    The wait is polled, so a close is seen while the child is still loading,
    and the child it would otherwise leave behind is terminated instead of
    staying resident after the session that asked for it is gone."""
    loading = threading.Event()
    release = threading.Event()

    def slow_load(repo):
        loading.set()
        release.wait(10)
        return _classify

    in_threads.setattr(emotion_model, "load_classifier", slow_load)
    worker = EmotionWorker("me/e2v")
    failure: list[BaseException] = []

    def start():
        try:
            worker.start()
        except BaseException as exc:
            failure.append(exc)

    thread = threading.Thread(target=start, daemon=True)
    thread.start()
    assert loading.wait(5)

    worker.close()

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not STARTED[0].was_terminated:
        time.sleep(0.01)
    assert STARTED[0].was_terminated  # the child was taken down, not kept
    release.set()
    thread.join(5)

    assert not thread.is_alive()
    assert not worker.is_started
    assert failure and "closed" in str(failure[0])


def test_a_closed_worker_starts_nothing_more(in_threads):
    worker = EmotionWorker("me/e2v")
    worker.close()

    with pytest.raises(RuntimeError, match="closed"):
        worker.start()


def test_load_classifier_reads_the_cached_copy_first(monkeypatch):
    asked = []

    def snapshot_download(repo, local_files_only=False):
        asked.append(local_files_only)
        return f"/cache/{repo}"

    class AutoModel:
        def __init__(self, model, disable_update):
            self.model = model

        def generate(self, samples, granularity, extract_embedding):
            return [{"labels": LABELS, "scores": SCORES}]

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(snapshot_download=snapshot_download),
    )
    monkeypatch.setitem(sys.modules, "funasr", SimpleNamespace(AutoModel=AutoModel))

    classify = emotion_model.load_classifier("me/e2v")

    assert asked == [True]
    assert classify(b"\x00\x00") == {"labels": LABELS, "scores": SCORES}


def test_make_expendable_asks_to_be_the_one_killed(monkeypatch, tmp_path):
    score = tmp_path / "oom_score_adj"
    score.write_text("0", encoding="utf-8")
    monkeypatch.setattr(emotion_model, "OOM_SCORE_PATH", str(score))

    emotion_model.make_expendable()

    assert score.read_text(encoding="utf-8") == "1000"


def test_make_expendable_is_quiet_where_there_is_no_such_file(
    monkeypatch, tmp_path, caplog
):
    score = tmp_path / "oom_score_adj"
    score.write_text("0", encoding="utf-8")
    monkeypatch.setattr(emotion_model, "OOM_SCORE_PATH", str(score))
    monkeypatch.setattr(emotion_model.os.path, "exists", lambda path: False)

    emotion_model.make_expendable()

    assert score.read_text(encoding="utf-8") == "0"
