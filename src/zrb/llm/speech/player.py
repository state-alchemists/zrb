"""Playing speech: one background thread per `Speaker`, one voice at a time.

Playback holds a lock file, so two zrb sessions never talk over each other,
and `is_speaking` reports it, so dictation can ignore the microphone while
zrb's own voice is in the room.
"""

from __future__ import annotations

import atexit
import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import replace

from zrb.config.config import CFG
from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.builtin import get_speech_backend
from zrb.llm.speech.backend.utterance import Utterance
from zrb.llm.speech.config import SpeechConfig
from zrb.llm.speech.pcm_player import PcmUtterance
from zrb.llm.speech.pcm_player import is_available as is_in_process_available
from zrb.util.file_lock import FileLockTimeout, hold_file_lock

logger = logging.getLogger(__name__)

_state_lock = threading.Lock()
# How many utterances this process is playing now, across every speaker.
_playing_count = 0
# Lock file -> how many live speakers configured it. Counted, not a plain set,
# so a finished speaker takes its entry with it: `is_speaking` probes every
# path here on every captured audio block.
_lock_files: dict[str, int] = {}
_STALE_POLL_SECONDS = 0.1
IsStale = Callable[[], bool] | None


def is_speaking(lock_file: str | None = None) -> bool:
    """Whether this process, or a zrb session sharing a lock file with it, is
    playing speech.

    The lock files checked are *lock_file*, `CFG.LLM_SPEECH_LOCK_FILE`, and
    every one a live `Speaker` in this process uses, so dictation hears a
    speaker configured with its own lock file without being told about it.
    """
    with _state_lock:
        if _playing_count:
            return True
        lock_files = {*_lock_files, CFG.LLM_SPEECH_LOCK_FILE}
    if lock_file:
        lock_files.add(lock_file)
    return any(_is_locked(path) for path in lock_files)


def _register_lock_file(lock_file: str) -> None:
    with _state_lock:
        _lock_files[lock_file] = _lock_files.get(lock_file, 0) + 1


def _unregister_lock_file(lock_file: str) -> None:
    with _state_lock:
        if _lock_files.get(lock_file, 0) <= 1:
            _lock_files.pop(lock_file, None)
        else:
            _lock_files[lock_file] -= 1


def _is_locked(lock_file: str) -> bool:
    try:
        with hold_file_lock(lock_file, timeout=0):
            return False
    except FileLockTimeout:
        return True
    except OSError:
        return False


class Speaker:
    """Speaks queued text in order on background threads.

    One thread makes the audio and another plays it, so the next sentence is
    synthesized while the current one plays and follows it without a gap;
    at most one waits ready. The threads start on the first `say`. At exit, queued speech gets the
    config's ``drain_timeout`` to finish, since `zrb chat --message` exits
    right after its reply. *config* is a resolved `SpeechConfig`.
    """

    def __init__(self, config: SpeechConfig) -> None:
        self._config = config
        self._lock_file = config.lock_file or ""
        self._lock_file_held = bool(self._lock_file)
        if self._lock_file_held:
            _register_lock_file(self._lock_file)
        self._queue: "queue.Queue[tuple[str | Callable[[], str], IsStale] | None]" = (
            queue.Queue()
        )
        # Made but not yet played: what the player thread takes next.
        self._ready: "queue.Queue[tuple[Utterance, IsStale, int] | None]" = queue.Queue(
            maxsize=1
        )
        self._worker: threading.Thread | None = None
        self._player: threading.Thread | None = None
        # Hooks call `say` from worker threads, so starting the worker, and
        # tracking what it is playing, is guarded.
        self._lock = threading.Lock()
        self._playing: Utterance | None = None
        # Closed: `say` queues nothing more. Cut off: nothing more is played.
        self._is_closed = False
        self._is_cut_off = False
        # Bumped by `interrupt`: speech taken off the queue before it is
        # dropped rather than played late.
        self._generation = 0
        self.is_enabled = True

    def say(self, text: str, is_stale: "IsStale" = None) -> None:
        """Queue *text*; dropped while the speaker is disabled or closed.

        *is_stale*, when given, says the text no longer needs saying: it is
        then skipped if its turn has not come, or cut off if it is playing.
        """
        if text.strip():
            self._enqueue(text, is_stale)

    def say_later(self, produce: "Callable[[], str]") -> None:
        """Queue what *produce* returns, called on the speaker's thread when
        its turn comes; for text that takes a while to make, such as a
        summary, so it keeps its place and the exit drain waits for it."""
        self._enqueue(produce)

    def _enqueue(
        self, item: "str | Callable[[], str]", is_stale: "IsStale" = None
    ) -> None:
        if not self.is_enabled:
            return
        with self._lock:
            if self._is_closed:
                return
            if self._worker is None:
                self._worker = threading.Thread(
                    target=self._prepare_queue,
                    name=f"{CFG.ROOT_GROUP_NAME}-speech",
                    daemon=True,
                )
                self._player = threading.Thread(
                    target=self._play_ready,
                    name=f"{CFG.ROOT_GROUP_NAME}-speech-player",
                    daemon=True,
                )
                self._worker.start()
                self._player.start()
                atexit.register(self.drain)
            self._queue.put((item, is_stale))

    def clear(self) -> None:
        """Drop everything not yet spoken, including what is being
        synthesized now: it is dropped once made, not played late."""
        with self._lock:
            self._generation += 1
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        try:
            while True:
                entry = self._ready.get_nowait()
                if entry is None:
                    # The player's stop signal is not ours to drop.
                    self._ready.put_nowait(None)
                    break
                entry[0].cleanup()
        except queue.Empty:
            pass

    def pause(self) -> None:
        """Hold what is playing, for a user who may be talking over it; what
        is queued waits. Speech a player program is playing cannot pause, so
        it is interrupted instead."""
        with self._lock:
            playing = self._playing
        if playing is None:
            return
        if playing.is_pausable:
            playing.pause()
        else:
            self.interrupt()

    def resume(self) -> None:
        """Carry on after `pause`."""
        with self._lock:
            playing = self._playing
        if playing is not None:
            playing.resume()

    def interrupt(self) -> None:
        """Drop queued speech and stop what is playing, for a user who started
        talking over it. Unlike `close`, the speaker keeps speaking whatever
        is said after this."""
        with self._lock:
            self._generation += 1
            playing = self._playing
        self.clear()
        if playing is not None:
            playing.stop()

    def speak(self, text: str, is_stale: "IsStale" = None) -> None:
        """Speak *text* now, blocking; the local engine stands in for a
        backend that fails. *is_stale* as for `say`."""
        self._speak(text, is_stale, self._generation)

    def _speak(self, text: str, is_stale: "IsStale", generation: int) -> None:
        utterance = self._prepare(text, is_stale)
        if utterance is not None:
            self._play_prepared(utterance, is_stale, generation)

    def _prepare(self, text: str, is_stale: "IsStale") -> Utterance | None:
        if not text.strip() or (is_stale is not None and is_stale()):
            return None
        return self._create_with_fallback(text)

    def _play_prepared(
        self, utterance: Utterance, is_stale: "IsStale", generation: int
    ) -> None:
        with self._lock:
            if (
                self._is_cut_off
                or not self.is_enabled
                or generation != self._generation
                or (is_stale is not None and is_stale())
            ):
                utterance.cleanup()
                return
            self._playing = utterance
        played = threading.Event()
        if is_stale is not None:
            threading.Thread(
                target=_stop_when_stale,
                args=(utterance, is_stale, played),
                daemon=True,
            ).start()
        try:
            play(utterance, self._config)
        finally:
            played.set()
            with self._lock:
                self._playing = None
            utterance.cleanup()

    def _create_with_fallback(self, text: str) -> Utterance | None:
        for backend in self._get_backends():
            try:
                return self._create_utterance(backend, text)
            except Exception as exc:
                logger.warning(f"Speech backend {backend.name} failed: {exc}")
        return None

    def _create_utterance(self, backend: AnySpeechBackend, text: str) -> Utterance:
        """Played by zrb itself when it can be, else by a player program:
        audio *backend* fails to render is still spoken its usual way."""
        player = (self._config.player or "auto").strip().lower()
        if player != "command" and is_in_process_available():
            try:
                audio = backend.create_audio(text)
            except Exception as exc:
                logger.warning(
                    f"Speech backend {backend.name} could not render audio for "
                    f"zrb to play ({exc}); a player program plays it instead"
                )
                audio = None
            if audio is not None:
                return PcmUtterance(audio)
        return backend.create_utterance(text)

    def _get_backends(self) -> list[AnySpeechBackend]:
        config = self._config
        requested = get_speech_backend(config.backend or "auto", config)
        # The configured voice names one of the requested backend's voices.
        local = get_speech_backend("auto", replace(config, voice=""))
        if local.name == requested.name:
            return [requested]
        return [requested, local]

    def _prepare_queue(self) -> None:
        """Make each queued text's audio, handing it to the player thread."""
        while (entry := self._queue.get()) is not None:
            item, is_stale = entry
            generation = self._generation
            try:
                utterance = self._prepare(item() if callable(item) else item, is_stale)
            except Exception as exc:
                logger.warning(f"Speech failed: {exc}")
                continue
            if utterance is not None:
                self._ready.put((utterance, is_stale, generation))
        self._ready.put(None)

    def _play_ready(self) -> None:
        while (entry := self._ready.get()) is not None:
            try:
                self._play_prepared(*entry)
            except Exception as exc:
                logger.warning(f"Speech failed: {exc}")

    def close(self) -> None:
        """Drop queued speech, cut off what is playing, stop the thread and
        release the lock file, for a session that is over."""
        self._cut_off()
        # Not joined: a worker still synthesizing or waiting for the audio
        # lock plays nothing now, and would hold up the session's teardown.
        self._stop(join_timeout=0)

    def drain(self) -> None:
        """Let queued speech finish, for up to the config's
        ``drain_timeout``, then stop the thread and cut off anything still
        playing, so no player outlives zrb."""
        with self._lock:
            self._is_closed = True
        self._stop(self._config.drain_timeout)
        self._cut_off()

    def _cut_off(self) -> None:
        with self._lock:
            self._is_closed = self._is_cut_off = True
            playing = self._playing
        self.clear()
        if playing is not None:
            playing.stop()

    def _stop(self, join_timeout: float | None) -> None:
        if self._lock_file_held:
            self._lock_file_held = False
            _unregister_lock_file(self._lock_file)
        with self._lock:
            worker, self._worker = self._worker, None
            player, self._player = self._player, None
        if worker is None:
            return
        atexit.unregister(self.drain)
        self._queue.put(None)
        deadline = None if join_timeout is None else time.monotonic() + join_timeout
        worker.join(join_timeout)
        if player is not None:
            remaining = None if deadline is None else deadline - time.monotonic()
            player.join(None if remaining is None else max(remaining, 0))


def play(utterance: Utterance, config: SpeechConfig) -> None:
    """Play *utterance* while holding the resolved *config*'s audio lock.

    Dropped, not queued, when another session holds the lock for more than
    ``lock_timeout``: falling behind would speak stale replies.
    """
    try:
        with hold_file_lock(
            config.lock_file or CFG.LLM_SPEECH_LOCK_FILE, timeout=config.lock_timeout
        ):
            _set_playing(+1)
            try:
                utterance.play(config.player_timeout or None)
            finally:
                _set_playing(-1)
    except FileLockTimeout:
        logger.warning("Speech dropped: another session held the audio device")
    except Exception as exc:
        logger.warning(f"Speech playback failed: {exc}")


def _stop_when_stale(
    utterance: Utterance, is_stale: "Callable[[], bool]", played: threading.Event
) -> None:
    while not played.wait(_STALE_POLL_SECONDS):
        if is_stale():
            utterance.stop()
            return


def _set_playing(change: int) -> None:
    global _playing_count
    with _state_lock:
        _playing_count += change
