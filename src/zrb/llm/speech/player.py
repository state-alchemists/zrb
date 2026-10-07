"""Play speech on background threads, one voice at a time."""

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
# Number of utterances currently playing in this process.
_playing_count = 0
# Lock file reference counts for live speakers.
_lock_files: dict[str, int] = {}
_STALE_POLL_SECONDS = 0.1
_PLAYERS = ("auto", "command")
IsStale = Callable[[], bool] | None


def is_speaking(lock_file: str | None = None) -> bool:
    """Whether this process or a session sharing a lock file is speaking."""
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
    """Speak queued text in order on background threads."""

    def __init__(self, config: SpeechConfig) -> None:
        self._config = config
        self._player_mode = _resolve_player(config.player)
        # Set after an output-device failure to avoid retrying.
        self._is_device_unavailable = False
        self._lock_file = config.lock_file or ""
        self._lock_file_held = bool(self._lock_file)
        if self._lock_file_held:
            _register_lock_file(self._lock_file)
        self._queue: (
            "queue.Queue[tuple[str | Callable[[], str], IsStale, int] | None]"
        ) = queue.Queue()
        # Made but not yet played: what the player thread takes next.
        self._ready: "queue.Queue[tuple[Utterance, IsStale, int] | None]" = queue.Queue(
            maxsize=1
        )
        # Set when the player has finished; the worker then closes backends.
        self._player_finished = threading.Event()
        self._worker: threading.Thread | None = None
        self._player: threading.Thread | None = None
        # Guards worker startup and current playback.
        self._lock = threading.Lock()
        self._playing: Utterance | None = None
        # Cached backends may hold models or running pipelines.
        self._backends: list[AnySpeechBackend] | None = None
        # Paused utterances wait on `_unpaused`.
        self._is_paused = False
        self._unpaused = threading.Condition(self._lock)
        # Closed stops queuing; cut off stops playback.
        self._is_closed = False
        self._is_cut_off = False
        # Generation invalidates interrupted queue entries.
        self._generation = 0
        self.is_enabled = True

    def say(self, text: str, is_stale: "IsStale" = None) -> None:
        """Queue *text* unless it is blank, disabled, or stale."""
        if text.strip():
            self._enqueue(text, is_stale)

    def say_later(self, produce: "Callable[[], str]") -> None:
        """Queue text produced on the speaker's thread."""
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
                atexit.register(self._drain_at_exit)
            self._queue.put((item, is_stale, self._generation))

    def clear(self) -> None:
        """Drop queued and currently synthesized speech."""
        with self._lock:
            self._generation += 1
            self._unpaused.notify_all()
        try:
            while True:
                if self._queue.get_nowait() is None:
                    # The worker's stop signal is not ours to drop either.
                    self._queue.put_nowait(None)
                    break
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
        """Pause current in-process audio and defer queued speech."""
        with self._lock:
            self._is_paused = True
            playing = self._playing
            if playing is None:
                return
            if playing.is_pausable:
                playing.pause()
            else:
                playing.stop()

    def resume(self) -> None:
        """Carry on after `pause`."""
        with self._lock:
            self._is_paused = False
            self._unpaused.notify_all()
            if self._playing is not None:
                self._playing.resume()

    def interrupt(self) -> None:
        """Drop queued speech and stop current playback."""
        with self._lock:
            self._generation += 1
            self._is_paused = False
            self._unpaused.notify_all()
            playing = self._playing
        self.clear()
        if playing is not None:
            playing.stop()

    def speak(self, text: str, is_stale: "IsStale" = None) -> None:
        """Speak *text* now, falling back locally when needed."""
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
            # Wait while paused unless this utterance was invalidated.
            while (
                self._is_paused
                and not self._is_closed
                and generation == self._generation
            ):
                self._unpaused.wait()
            if (
                self._is_cut_off
                or (self._is_paused and self._is_closed)
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
        """Create *text* with the first usable backend."""
        backends = self._get_backends()
        for index, backend in enumerate(backends):
            if backend.needs_zrb_playback and not self._is_in_process_wanted():
                # Without in-process playback, this backend cannot produce audio.
                continue
            try:
                return self._create_utterance(backend, text, backends[index + 1 :])
            except Exception as exc:
                logger.warning(f"Speech backend {backend.name} failed: {exc}")
        return None

    def _create_utterance(
        self,
        backend: AnySpeechBackend,
        text: str,
        later: "list[AnySpeechBackend]",
    ) -> Utterance:
        """Create an utterance, using a later backend if needed."""
        if self._is_in_process_wanted():
            try:
                audio = backend.create_audio(text)
            except Exception as exc:
                logger.warning(
                    f"Speech backend {backend.name} could not render audio to "
                    f"play in process ({exc}); a player program plays it instead"
                )
                audio = None
            if audio is not None:
                return PcmUtterance(
                    audio,
                    block_frames=self._config.player_block_frames,
                    read_ahead=self._config.player_read_ahead,
                    fallback=self._program_fallback(backend, later, text),
                    on_device_error=self._handle_device_error,
                )
        return backend.create_utterance(text)

    def _program_fallback(
        self,
        backend: AnySpeechBackend,
        later: "list[AnySpeechBackend]",
        text: str,
    ) -> Callable[[], Utterance] | None:
        """Return a player-program fallback for *text*, if available."""
        if not backend.needs_zrb_playback:
            return lambda: backend.create_utterance(text)
        alternatives = [other for other in later if not other.needs_zrb_playback]
        if not alternatives:
            return None
        spoken_by = alternatives[0]
        return lambda: spoken_by.create_utterance(text)

    def _is_in_process_wanted(self) -> bool:
        return (
            self._player_mode != "command"
            and not self._is_device_unavailable
            and is_in_process_available()
        )

    def _handle_device_error(self, exc: Exception) -> None:
        with self._lock:
            is_first = not self._is_device_unavailable
            self._is_device_unavailable = True
        if is_first:
            logger.warning(
                f"Could not open the audio device to play speech in process "
                f"({exc}); a player program plays it for the rest of the session"
            )

    def _get_backends(self) -> list[AnySpeechBackend]:
        """Return this speaker's cached backends."""
        if self._backends is None:
            config = self._config
            requested = get_speech_backend(config.backend or "auto", config)
            # Resolve the local fallback without the configured voice.
            local = get_speech_backend("auto", replace(config, voice=""))
            if local.name == requested.name:
                self._backends = [requested]
            else:
                self._backends = [requested, local]
        return self._backends

    def _prepare_queue(self) -> None:
        """Make each queued text's audio, handing it to the player thread."""
        while (entry := self._queue.get()) is not None:
            item, is_stale, generation = entry
            try:
                text = item() if callable(item) else item
                utterance = self._prepare(text, is_stale)
            except Exception as exc:
                logger.warning(f"Speech failed: {exc}")
                continue
            if utterance is None:
                continue
            if self._is_cut_off:
                utterance.cleanup()
                continue
            self._ready.put((utterance, is_stale, generation))
        self._ready.put(None)
        # The worker closes backends after the player finishes consuming audio.
        self._player_finished.wait()
        self._close_backends()

    def _play_ready(self) -> None:
        try:
            while (entry := self._ready.get()) is not None:
                try:
                    self._play_prepared(*entry)
                except Exception as exc:
                    logger.warning(f"Speech failed: {exc}")
        finally:
            # The worker may close backends after this signal.
            self._player_finished.set()

    def close(self) -> None:
        """Stop playback and release the lock file."""
        self._cut_off()
        # Do not wait for a worker still synthesizing or waiting for the lock.
        self._stop(join_timeout=0)

    def drain(self) -> None:
        """Drain queued speech for the configured timeout, then stop."""
        with self._lock:
            self._is_closed = True
            self._unpaused.notify_all()
        try:
            self._stop(self._config.drain_timeout)
        finally:
            self._cut_off()

    def _drain_at_exit(self) -> None:
        # Ctrl+C during exit should not add a traceback.
        try:
            self.drain()
        except KeyboardInterrupt:
            pass

    def _cut_off(self) -> None:
        with self._lock:
            self._is_closed = self._is_cut_off = True
            self._unpaused.notify_all()
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
        if worker is not None:
            atexit.unregister(self._drain_at_exit)
            self._queue.put(None)
            deadline = None if join_timeout is None else time.monotonic() + join_timeout
            worker.join(join_timeout)
            if player is not None:
                remaining = None if deadline is None else deadline - time.monotonic()
                player.join(None if remaining is None else max(remaining, 0))
        else:
            # Synchronous `speak` can build backends without a worker.
            self._close_backends()

    def _close_backends(self) -> None:
        """Let the backends go for good; a closed speaker builds no more."""
        with self._lock:
            backends, self._backends = self._backends, []
        for backend in backends or []:
            backend.close()


def _resolve_player(player: str | None) -> str:
    mode = (player or "auto").strip().lower()
    if mode in _PLAYERS:
        return mode
    logger.warning(f"Unknown speech player {player!r}: use auto or command; auto it is")
    return "auto"


def play(utterance: Utterance, config: SpeechConfig) -> None:
    """Play *utterance* while holding the resolved audio lock."""
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
