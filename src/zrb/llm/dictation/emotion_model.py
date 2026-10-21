"""emotion2vec+, and where it is loaded: in a child process, or in this one.

funasr loads the model's checkpoint and then copies it into the model, so the
load costs far more than the model keeps. Measured on a 6.8 GB WSL2 machine,
for `emotion2vec_plus_base`: 1.1 GB on disk, 977 MB kept, **2.9 GB peak**. In a
chat process that already holds the transcriber and the speech model, that peak
is what the kernel's OOM killer picked — four times in three days, at 3 GB of
anonymous memory.

`EmotionWorker` keeps the model in a child process instead. The spike lands
there, the chat's own footprint stays what the transcriber and the voice already
cost, and the child asks to be picked first if the machine still runs out
(`make_expendable`, since address space says nothing about what torch holds: the
chat's `VmPeak` is 8 GB while its resident set is 2 GB). A child that dies costs
a tone, not the conversation.

Why the load is not capped with `RLIMIT_AS`: torch reserves a large, mostly
untouched address space, so a cap low enough to matter fails the import long
before the machine is actually out of memory.
"""

from __future__ import annotations

import importlib
import logging
import multiprocessing
import os
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from zrb.llm.dictation.hub import get_hub_path
from zrb.llm.util.model_load import heavy_model_load

if TYPE_CHECKING:
    from multiprocessing.connection import Connection
    from multiprocessing.process import BaseProcess

logger = logging.getLogger(__name__)

#: Classifies one clip, returning emotion2vec's labels and their scores.
Classify = Callable[[object], dict[str, list[object]]]

#: What funasr and torch raise loading the model or classifying a clip, and what
#: the worker itself raises for a child that died. Any of them costs only the
#: tone, never the user's words. `MemoryError` is here because the machine is
#: what fails, and a tone nobody hears is still better than a crash.
MODEL_ERRORS = (
    ImportError,
    OSError,
    RuntimeError,
    ValueError,
    KeyError,
    IndexError,
    TypeError,
    AttributeError,
    AssertionError,
    MemoryError,
)

#: How long the child is given to start and to load the model: a cold load is
#: ~20 s on a slow disk, and the number is generous so a slow machine is not
#: mistaken for a broken one.
READY_TIMEOUT_SECONDS = 120.0

#: How long one readiness poll waits before the worker's closed flag is read
#: again: short enough that a session ending mid-load stops its child at once,
#: long enough not to spin. A child that is loading its model reads nothing from
#: the pipe, so waiting on it in one long call is how the child outlived the
#: session that closed it.
READY_POLL_SECONDS = 0.2

#: How long a child is given to end once it is asked to. One reading its pipe
#: ends at once; one busy loading its model cannot answer at all, so a longer
#: grace only keeps that model resident.
STOP_GRACE_SECONDS = 1.0

#: How many clips in a row a child may fail to classify before its worker is
#: restarted. One unreadable clip is the clip's — the next one is other audio,
#: and reloading a 1 GB model for it costs more than the tone — while a child
#: that fails on every clip is the worker's, and keeping it would leave the
#: session without tones until it ends.
CLIP_ERRORS_BEFORE_RESTART = 2

#: How long one clip's classification may take. Measured at ~0.3 s, so a child
#: silent this long is wedged, not slow. The turn waits for its tone, so this is
#: also the longest a wedged child can hold a reply back.
CLASSIFY_TIMEOUT_SECONDS = 5.0

#: How many times a child may die before the tone is given up on for the
#: session: restarting into the same out-of-memory over and over is worse than
#: no tone at all.
MAX_DEATHS = 3

#: Where Linux takes a process's willingness to be the one the OOM killer picks.
OOM_SCORE_PATH = "/proc/self/oom_score_adj"


def load_classifier(repo: str) -> Classify:
    """Load emotion2vec+ from the Hugging Face repo *repo*, in this process."""
    # The slot is taken before the imports, not after: importing funasr brings
    # torch with it (517 MB measured), so an import outside the slot is half a
    # spike stacking on whatever else is loading. The local speech service
    # takes it the same way, around its factory and its imports both.
    with heavy_model_load("the emotion model"):
        # lazy: heavy third-party — huggingface_hub. funasr and torch are not zrb
        # dependencies, so funasr is imported by name.
        from huggingface_hub import snapshot_download

        auto_model = importlib.import_module("funasr").AutoModel
        # A local directory, so funasr loads it as it is instead of looking the
        # name up on its default hub, ModelScope.
        model = auto_model(
            model=get_hub_path(snapshot_download, repo), disable_update=True
        )
    return lambda samples: model.generate(
        samples, granularity="utterance", extract_embedding=False
    )[0]


class EmotionWorker:
    """emotion2vec+ in a child process, loaded by `start`."""

    def __init__(self, repo: str) -> None:
        self._repo = repo
        self._classify: Classify | None = None
        self._process: "BaseProcess | None" = None
        self._connection: "Connection | None" = None
        # Guards the fields above, held only briefly.
        self._state = threading.Lock()
        # Serializes starting, so two askers share one child.
        self._starting = threading.Lock()
        # Serializes requests into the child, which classifies one clip at a time.
        self._requesting = threading.Lock()
        self._deaths = 0
        # Clips in a row the child could not classify, held with `_deaths`.
        self._clip_errors = 0
        self._is_closed = False

    @property
    def is_started(self) -> bool:
        """Whether the child is running with its model loaded."""
        with self._state:
            return self._classify is not None

    def start(self) -> Classify:
        """Start the child and load the model in it, returning the classify
        callable, or raising why it could not."""
        with self._starting:
            with self._state:
                if self._classify is not None:
                    return self._classify
                if self._is_closed:
                    raise RuntimeError(
                        "the emotion worker was closed, so it starts no child "
                        "and this clip's tone is not heard"
                    )
                deaths = self._deaths
            if deaths >= MAX_DEATHS:
                raise RuntimeError(
                    f"the emotion worker was killed {deaths} times; this "
                    "machine has no room for it beside the chat"
                )
            with heavy_model_load("the emotion model"):
                process, connection = _spawn_child(self._repo)
                try:
                    status, reason = self._wait_for_ready(connection)
                except BaseException:
                    _stop_child(process, connection)
                    raise
            if status != "ready":
                _stop_child(process, connection)
                raise RuntimeError(reason or "the emotion model did not load")
            with self._state:
                is_closed = self._is_closed
                if not is_closed:
                    self._process, self._connection = process, connection
                    self._classify = self._request
                    # A fresh child starts from none: the count is of clips one
                    # child failed in a row.
                    self._clip_errors = 0
            if is_closed:
                # Closed while the model loaded: nobody wants this child. It is
                # stopped outside the lock, since stopping one waits for it.
                _stop_child(process, connection)
                raise RuntimeError(
                    "the emotion worker was closed before its model finished "
                    "loading, so no tone is heard"
                )
            return self._request

    def _wait_for_ready(self, connection: "Connection") -> "tuple[str, str]":
        """The child's first message: ``("ready", "")`` or ``("error", reason)``.

        Polled in slices rather than in one long wait, so a `close` landing
        while the model loads is noticed: the child it would otherwise leave
        behind is exactly what a session that ended must not keep."""
        deadline = time.monotonic() + READY_TIMEOUT_SECONDS
        while True:
            if self._is_closed:
                raise RuntimeError(
                    "the emotion worker was closed while its model loaded, so "
                    "no tone is heard"
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(
                    "the emotion worker said nothing for "
                    f"{READY_TIMEOUT_SECONDS:g}s while loading its model"
                )
            try:
                if not connection.poll(min(READY_POLL_SECONDS, remaining)):
                    continue
                reply = connection.recv()
            except (EOFError, OSError) as exc:
                raise RuntimeError(
                    f"the emotion worker stopped while loading its model ({exc})"
                ) from exc
            return str(reply[0]), str(reply[1])

    def close(self) -> None:
        """Stop the child without waiting for it to end; one already gone, and
        one still loading, is nothing to do here.

        The session's teardown calls this, and a child that does not answer
        costs `_stop_child` its grace and then a terminate: that wait is the
        stopping thread's, not the teardown's. A child that is loading its model
        reads nothing from the pipe, so this cannot stop it: the wait is polled
        (`_wait_for_ready`), sees the closed flag within `READY_POLL_SECONDS`,
        and stops the child it started.
        """
        with self._state:
            self._is_closed = True
            process, connection = self._process, self._connection
            self._process, self._connection, self._classify = None, None, None
        if process is None and connection is None:
            return
        threading.Thread(
            target=_stop_child,
            args=(process, connection),
            name="zrb-emotion-stop",
            daemon=True,
        ).start()

    def _request(self, samples: object) -> dict[str, list[object]]:
        """Send one clip to the child and wait for its verdict."""
        with self._requesting:
            with self._state:
                connection = self._connection
            if connection is None:
                raise RuntimeError(
                    "the emotion worker is not running, so this clip's tone "
                    "is not heard"
                )
            try:
                connection.send(samples)
                if not connection.poll(CLASSIFY_TIMEOUT_SECONDS):
                    # A child that says nothing for a clip is wedged, not slow
                    # (the measurement is ~0.3 s), and it will not answer the
                    # next clip either. It is stopped like a dead one: asking it
                    # again would cost every later utterance the whole timeout
                    # and keep its model resident for a worker nobody hears.
                    self._forget_child()
                    raise RuntimeError(
                        "the emotion worker said nothing for "
                        f"{CLASSIFY_TIMEOUT_SECONDS:g}s"
                    )
                verdict = _read_reply(connection.recv())
            except (EOFError, OSError) as exc:
                # The child is gone (an out-of-memory kill, most likely). The
                # next utterance starts another, up to `MAX_DEATHS`.
                self._forget_child()
                raise RuntimeError(f"the emotion worker stopped ({exc})") from exc
            except _ChildSaidError:
                # The child is alive and answered: it could not classify this
                # clip. That is the clip's problem once, and the worker's when
                # it happens again.
                self._note_clip_error()
                raise
            with self._state:
                self._clip_errors = 0
            return verdict

    def _note_clip_error(self) -> None:
        """Count a clip the child could not classify, and restart the worker
        once every clip fails.

        A child that answers an error is alive and holding its model, so the
        clip, not the worker, is what went wrong — the next clip is other
        audio. A second failure in a row is the worker's, and it is forgotten
        like a dead one: a model that fails on everything must not leave the
        session without tones, nor hold its share of the machine, until it
        ends. A fresh child starts from none, so each one gets the same two
        clips before it is suspected."""
        with self._state:
            self._clip_errors += 1
            is_worn_out = self._clip_errors >= CLIP_ERRORS_BEFORE_RESTART
        if is_worn_out:
            self._forget_child()

    def _forget_child(self) -> None:
        with self._state:
            process, connection = self._process, self._connection
            self._process, self._connection, self._classify = None, None, None
            self._deaths += 1
        _stop_child(process, connection)


def _spawn_child(repo: str) -> "tuple[BaseProcess, Connection]":
    """A started child process and this end of the pipe to it."""
    # spawn, not fork: the chat holds torch threads, and a forked child of a
    # process with native threads is the shape that crashes.
    context = multiprocessing.get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=True)
    process = context.Process(
        target=_serve, args=(child_connection, repo), daemon=True
    )
    process.start()
    child_connection.close()
    return process, parent_connection


class _ChildSaidError(RuntimeError):
    """The child was alive and answered: it could not classify that clip."""


def _read_reply(reply: "tuple[str, object]") -> dict[str, list[object]]:
    """What the child answered: its verdict, or why the clip had none."""
    status, value = reply[0], reply[1]
    if status != "tone":
        raise _ChildSaidError(str(value))
    return cast("dict[str, list[object]]", value)


def _stop_child(
    process: "BaseProcess | None", connection: "Connection | None"
) -> None:
    """Ask the child to end, and take it down if it does not."""
    if connection is not None:
        try:
            connection.send(None)
        except (EOFError, OSError):
            pass
        try:
            connection.close()
        except OSError:
            pass
    if process is None:
        return
    process.join(STOP_GRACE_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(5.0)


def _serve(connection: "Connection", repo: str) -> None:
    """The child: load the model in this process, then classify what it is sent.

    This runs in a process of its own, which is the point: the model's load
    spike lands here. `make_expendable` asks the kernel to kill this process
    rather than the chat if the machine runs out.
    """
    make_expendable()
    try:
        classify = load_classifier(repo)
    except MODEL_ERRORS as exc:
        _send_quietly(connection, ("error", str(exc) or type(exc).__name__))
        return
    _send_quietly(connection, ("ready", ""))
    try:
        for samples in iter(connection.recv, None):
            connection.send(_classify_one(classify, samples))
    except (EOFError, OSError):
        # The chat is gone or closed the pipe: nothing left to answer.
        return
    finally:
        connection.close()


def _classify_one(classify: Classify, samples: object) -> "tuple[str, object]":
    """One clip through the model, as a message the parent can read."""
    try:
        return "tone", classify(samples)
    except MODEL_ERRORS as exc:
        return "error", str(exc) or type(exc).__name__


def _send_quietly(connection: "Connection", reply: "tuple[str, str]") -> None:
    try:
        connection.send(reply)
    except (EOFError, OSError):
        pass


def make_expendable() -> None:
    """Say the OOM killer should pick this process, not the chat.

    Linux only, and only where it may be written: a machine that does not allow
    it leaves the process as ordinary as it was, which is what the debug line
    says.
    """
    if not os.path.exists(OOM_SCORE_PATH):
        return
    try:
        with open(OOM_SCORE_PATH, "w", encoding="utf-8") as score:
            score.write("1000")
    except OSError as exc:
        logger.debug(f"Could not ask the OOM killer to pick this process: {exc}")
