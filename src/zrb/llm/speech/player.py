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
from dataclasses import replace

from zrb.config.config import CFG
from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.builtin import get_speech_backend
from zrb.llm.speech.backend.utterance import Utterance
from zrb.llm.speech.config import SpeechConfig
from zrb.util.file_lock import FileLockTimeout, hold_file_lock

logger = logging.getLogger(__name__)

_state_lock = threading.Lock()
# How many utterances this process is playing now, across every speaker.
_playing_count = 0
# Every lock file a speaker in this process plays under.
_lock_files: set[str] = set()


def is_speaking(lock_file: str | None = None) -> bool:
    """Whether this process, or a zrb session sharing a lock file with it, is
    playing speech.

    The lock files checked are *lock_file*, `CFG.LLM_SPEECH_LOCK_FILE`, and
    every one a `Speaker` in this process uses, so dictation hears a speaker
    configured with its own lock file without being told about it.
    """
    with _state_lock:
        if _playing_count:
            return True
        lock_files = {*_lock_files, CFG.LLM_SPEECH_LOCK_FILE}
    if lock_file:
        lock_files.add(lock_file)
    return any(_is_locked(path) for path in lock_files)


def _is_locked(lock_file: str) -> bool:
    try:
        with hold_file_lock(lock_file, timeout=0):
            return False
    except FileLockTimeout:
        return True
    except OSError:
        return False


class Speaker:
    """Speaks queued text in order on a background thread.

    The thread starts on the first `say`. At exit, queued speech gets the
    config's ``drain_timeout`` to finish, since `zrb chat --message` exits
    right after its reply. *config* is a resolved `SpeechConfig`.
    """

    def __init__(self, config: SpeechConfig) -> None:
        self._config = config
        if config.lock_file:
            with _state_lock:
                _lock_files.add(config.lock_file)
        self._queue: "queue.Queue[str | None]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self.is_enabled = True

    def say(self, text: str) -> None:
        """Queue *text*; dropped while the speaker is disabled."""
        if not self.is_enabled or not text.strip():
            return
        if self._worker is None:
            self._worker = threading.Thread(
                target=self._play_queue,
                name=f"{CFG.ROOT_GROUP_NAME}-speech",
                daemon=True,
            )
            self._worker.start()
            atexit.register(self.drain)
        self._queue.put(text)

    def clear(self) -> None:
        """Drop everything not yet spoken."""
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass

    def speak(self, text: str) -> None:
        """Speak *text* now, blocking; the local engine stands in for a
        backend that fails."""
        utterance = self._create_with_fallback(text)
        if utterance is None:
            return
        try:
            play(utterance, self._config)
        finally:
            utterance.cleanup()

    def _create_with_fallback(self, text: str) -> Utterance | None:
        for backend in self._get_backends():
            try:
                return backend.create_utterance(text)
            except Exception as exc:
                logger.warning(f"Speech backend {backend.name} failed: {exc}")
        return None

    def _get_backends(self) -> list[AnySpeechBackend]:
        config = self._config
        requested = get_speech_backend(config.backend or "auto", config)
        # The configured voice names one of the requested backend's voices.
        local = get_speech_backend("auto", replace(config, voice=""))
        if local.name == requested.name:
            return [requested]
        return [requested, local]

    def _play_queue(self) -> None:
        while (text := self._queue.get()) is not None:
            try:
                self.speak(text)
            except Exception as exc:
                logger.warning(f"Speech failed: {exc}")

    def drain(self) -> None:
        """Let queued speech finish, for up to the config's
        ``drain_timeout``, then stop the thread."""
        worker, self._worker = self._worker, None
        if worker is None:
            return
        atexit.unregister(self.drain)
        self._queue.put(None)
        worker.join(self._config.drain_timeout)


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


def _set_playing(change: int) -> None:
    global _playing_count
    with _state_lock:
        _playing_count += change
