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
from zrb.llm.ambient_state import current_speech_voice
from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.builtin import get_speech_backend
from zrb.llm.speech.backend.utterance import Utterance
from zrb.llm.speech.config import SpeechConfig
from zrb.llm.speech.pcm_player import (
    PcmUtterance,
    guard_exit_handler,
)
from zrb.llm.speech.pcm_player import is_available as is_in_process_available
from zrb.llm.speech.pcm_player import (
    wait_for_streams_to_close,
)
from zrb.util.file_lock import FileLockTimeout, hold_file_lock

logger = logging.getLogger(__name__)

_state_lock = threading.Lock()
# Number of utterances currently playing in this process.
_playing_count = 0
# Lock file reference counts for live speakers.
_lock_files: dict[str, int] = {}
_STALE_POLL_SECONDS = 0.1
_PLAYERS = ("auto", "command")
# How long an output device that failed to open is left alone before a sentence
# tries it again: changing the output device fails the open while the system
# hands the audio over, and the device works a moment later.
_DEVICE_RETRY_SECONDS = 3.0
# How long closing or exiting waits for a stopped output stream to finish
# closing: long enough for the device to let go, short enough that a wedged one
# cannot keep the process from ending.
_STREAM_CLOSE_WAIT_SECONDS = 2.0
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


# Pipecat gives up on a service after this many silent sentences in a row.
_RENDER_FAILURES_BEFORE_RESTART = 3


class Speaker:
    """Speak queued text in order on background threads."""

    def __init__(self, config: SpeechConfig) -> None:
        self._config = config
        self._player_mode = _resolve_player(config.player)
        # When the output device last failed: no sentence goes to it for
        # `_DEVICE_RETRY_SECONDS` after that, then one tries it again.
        self._device_failed_at: float | None = None
        # Said once, however often the device fails.
        self._has_said_device_failed = False
        self._lock_file = config.lock_file or ""
        self._lock_file_held = bool(self._lock_file)
        if self._lock_file_held:
            _register_lock_file(self._lock_file)
        self._queue: (
            "queue.Queue[tuple[str | Callable[[], str], IsStale, int, str] | None]"
        ) = queue.Queue()
        # Made but not yet played: what the player thread takes next.
        self._ready: "queue.Queue[tuple[Utterance, IsStale, int] | None]" = queue.Queue(
            maxsize=1
        )
        # Set when the player has finished; the worker then closes backends.
        self._player_finished = threading.Event()
        self._worker: threading.Thread | None = None
        self._player: threading.Thread | None = None
        # Guards worker startup, current playback and the last device failure.
        self._lock = threading.Lock()
        self._playing: Utterance | None = None
        # Cached backends may hold models or running pipelines.
        self._backends: list[AnySpeechBackend] | None = None
        # Which of the cached ones zrb built itself: a backend the caller
        # supplied is theirs to close, and outlives this speaker.
        self._owned_backends: list[AnySpeechBackend] = []
        # The prepare thread and the warm-up thread may both build backends.
        self._building = threading.Lock()
        # The backend whose in-process renders are failing, and how many in a row.
        self._failing_backend: AnySpeechBackend | None = None
        self._failed_renders = 0
        # Whether a warm-up is running, and whether this backend set was warmed
        # once: the model behind it loads once, whatever asks again. The
        # generation tells a warm-up of a set that `restart_backends` has since
        # replaced from the one that is current now.
        self._is_warming_up = False
        self._is_warmed_up = False
        self._warm_up_generation = 0
        # Set when that backend is dead; the drop waits for the next sentence.
        self._is_restart_pending = False
        # Paused utterances wait on `_unpaused`.
        self._is_paused = False
        self._unpaused = threading.Condition(self._lock)
        # Closed stops queuing; cut off stops playback.
        self._is_closed = False
        self._is_cut_off = False
        # Generation invalidates interrupted queue entries.
        self._generation = 0
        self.is_enabled = True

    def say(self, text: str, is_stale: "IsStale" = None, voice: str = "") -> None:
        """Queue *text* unless it is blank, disabled, or stale, to be said in
        *voice* (empty: the configured one)."""
        if text.strip():
            self._enqueue(text, is_stale, voice)

    def say_later(self, produce: "Callable[[], str]") -> None:
        """Queue text produced on the speaker's thread."""
        self._enqueue(produce)

    def _enqueue(
        self,
        item: "str | Callable[[], str]",
        is_stale: "IsStale" = None,
        voice: str = "",
    ) -> None:
        if not self.is_enabled:
            return
        if self._worker is None:
            self._import_audio_before_exit_handler()
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
            self._queue.put((item, is_stale, self._generation, voice))

    def _import_audio_before_exit_handler(self) -> None:
        """Import sounddevice before `_drain_at_exit` is registered.

        sounddevice terminates PortAudio from its own exit handler, and exit
        handlers run last-registered first. Importing it later, when the first
        sentence is prepared, would make it terminate PortAudio while speech is
        still playing, before `_drain_at_exit` had stopped anything."""
        if self._player_mode != "command" and is_in_process_available():
            guard_exit_handler()

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
        """Speak *text* now, falling back locally when needed.

        Blank, stale, muted or interrupted text is skipped. When nothing could
        be said, this raises: `RuntimeError` when no backend made the speech,
        `FileLockTimeout` when another session held the audio device, or the
        player's own error.
        """
        # Read before synthesis, so an interrupt during it drops this text.
        generation = self._generation
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

    def _create_with_fallback(self, text: str) -> Utterance:
        """Create *text* with the first usable backend, or raise why none could."""
        backends = self._get_backends()
        failures: list[str] = []
        for index, backend in enumerate(backends):
            later = backends[index + 1 :]
            if backend.needs_zrb_playback and not self._should_speak_in_process(later):
                # Without in-process playback, this backend cannot produce audio.
                continue
            try:
                return self._create_utterance(backend, text, later)
            except Exception as exc:
                logger.warning(f"Speech backend {backend.name} failed: {exc}")
                failures.append(f"{backend.name}: {exc}")
        reason = "; ".join(failures) or "none can play here"
        raise RuntimeError(f"No speech backend could speak ({reason})")

    def _create_utterance(
        self,
        backend: AnySpeechBackend,
        text: str,
        later: "list[AnySpeechBackend]",
    ) -> Utterance:
        """Create an utterance, using a later backend if needed."""
        if self._should_speak_in_process(later):
            try:
                audio = backend.create_audio(text)
            except Exception as exc:
                self._handle_render_failure(backend)
                logger.warning(
                    f"Speech backend {backend.name} could not render audio to play "
                    f"in process ({exc}); {self._what_speaks_it(backend, later)}"
                )
                audio = None
            else:
                self._handle_render_success(backend)
            if audio is not None:
                return PcmUtterance(
                    audio,
                    block_frames=self._config.player_block_frames,
                    read_ahead=self._config.player_read_ahead,
                    fallback=self._program_fallback(backend, later, text),
                    on_device_error=self._handle_device_error,
                    device_is_resting=self._is_device_resting,
                )
        return backend.create_utterance(text)

    def _stand_ins(self, later: "list[AnySpeechBackend]") -> "list[AnySpeechBackend]":
        """The later backends that can play a sentence through a program."""
        return [other for other in later if not other.needs_zrb_playback]

    def _what_speaks_it(
        self, backend: AnySpeechBackend, later: "list[AnySpeechBackend]"
    ) -> str:
        """What speaks a sentence *backend* could not render."""
        if not backend.needs_zrb_playback or self._stand_ins(later):
            return "a player program plays it instead"
        return "this sentence goes unsaid"

    def _program_fallback(
        self,
        backend: AnySpeechBackend,
        later: "list[AnySpeechBackend]",
        text: str,
    ) -> Callable[[], Utterance] | None:
        """Return a player-program fallback for *text*, if available."""
        if not backend.needs_zrb_playback:
            return lambda: backend.create_utterance(text)
        stand_ins = self._stand_ins(later)
        if not stand_ins:
            return None
        spoken_by = stand_ins[0]
        return lambda: spoken_by.create_utterance(text)

    def _can_play_in_process(self) -> bool:
        """Whether zrb may play a sentence itself at all."""
        return self._player_mode != "command" and is_in_process_available()

    def _should_speak_in_process(self, later: "list[AnySpeechBackend]") -> bool:
        """Whether zrb plays a sentence's own audio rather than a stand-in
        speaking it.

        The device that just failed is left alone only while a later backend can
        speak the sentence instead. A voice with no such stand-in keeps its own
        audio, so changing the output device costs a reply its pause, never its
        voice."""
        if not self._can_play_in_process():
            return False
        if not self._is_device_resting():
            return True
        return not self._stand_ins(later)

    def _is_device_resting(self) -> bool:
        """Whether the output device failed too recently for a sentence to try
        it again as it is: a player program speaks it instead where there is
        one, and where there is not, the sentence opens a PortAudio started
        again, which reads the devices the machine has now."""
        with self._lock:
            failed_at = self._device_failed_at
        if failed_at is None:
            return False
        return time.monotonic() < failed_at + _DEVICE_RETRY_SECONDS

    def _handle_device_error(self, exc: Exception) -> None:
        with self._lock:
            is_first = not self._has_said_device_failed
            self._has_said_device_failed = True
            self._device_failed_at = time.monotonic()
        if is_first:
            logger.warning(
                f"Could not use the audio device to play speech in process "
                f"({exc}); it is left alone for {_DEVICE_RETRY_SECONDS:g}s, and "
                "the devices are read again before it is tried"
            )

    def warm_up(self) -> None:
        """Load a local in-process backend's model on a thread of its own, so
        the first sentence does not wait for it. One word is made and never
        played.

        Asked for at the start of every turn and answered once per backend set:
        a call made while one is loading, or after one has loaded, does nothing.
        The model is what the wait was ever for — a thread per turn queued
        behind the same load is how one chat ended up with 38 of them parked.

        The set this warm-up belongs to is read here, with the generation, when
        it is already cached: a set built later is the thread's to build, and it
        re-reads the generation before warming what it got.
        """
        with self._lock:
            if self._is_warmed_up or self._is_warming_up or self._is_closed:
                return
            self._is_warming_up = True
            generation = self._warm_up_generation
            backends = self._backends
        threading.Thread(
            target=self._warm_up,
            args=(generation, backends),
            name=f"{CFG.ROOT_GROUP_NAME}-speech-warm-up",
            daemon=True,
        ).start()

    def _warm_up(
        self, generation: int, backends: "list[AnySpeechBackend] | None"
    ) -> None:
        """Warm the backend set once, whatever the probe came to: a model that
        did not load is the first sentence's to load.

        Only the warm-up of the current set says the set is warm. One that a
        `restart_backends` overtook warmed models the fresh set does not hold,
        so its completion leaves the flag down and the next `warm_up` warms the
        set that is there now."""
        try:
            self._warm_one_word(generation, backends)
        finally:
            with self._lock:
                if generation == self._warm_up_generation:
                    self._is_warming_up = False
                    self._is_warmed_up = True

    def _is_stale(self, generation: int) -> bool:
        """Whether `restart_backends` has replaced the set since *generation*."""
        with self._lock:
            return generation != self._warm_up_generation

    def _warm_one_word(
        self, generation: int, backends: "list[AnySpeechBackend] | None"
    ) -> None:
        try:
            if self._is_stale(generation):
                # A restart replaced the set this warm-up was started for. The
                # old one is not worth warming — it is closed — and the fresh
                # one is the next `warm_up`'s, which would otherwise probe the
                # same backend beside this thread and load its model twice.
                return
            if backends is None:
                backends = self._get_backends()
                if self._is_stale(generation):
                    # Overtaken while it built the set: what it got is the
                    # fresh generation's, and the next turn warms it.
                    return
            backend = backends[0]
            # A remote voice would bill a word nobody hears; the fallback is
            # never tried for the same reason.
            if not (
                backend.is_local
                and backend.needs_zrb_playback
                and self._can_play_in_process()
            ):
                return
            # A probe, not a sentence: no utterance, and a failure is not one
            # of the failures that drop the backend the sentences are spoken by.
            audio = backend.create_audio("Hi.")
            if audio is not None:
                audio.close()
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            # The first sentence tries again and reports a failure itself.
            logger.debug(f"Speech warm-up failed: {exc}")

    def _handle_render_failure(self, backend: AnySpeechBackend) -> None:
        """Count *backend*'s failures in a row; only its own renders end them."""
        with self._lock:
            if backend is not self._failing_backend:
                self._failing_backend = backend
                self._failed_renders = 0
            self._failed_renders += 1
            if self._failed_renders < _RENDER_FAILURES_BEFORE_RESTART:
                return
            # Dropped before the next sentence, not under this one: the
            # sentence still to be made from `backend` would find it closed.
            self._is_restart_pending = True

    def _handle_render_success(self, backend: AnySpeechBackend) -> None:
        """Forget *backend*'s failures: it renders again."""
        with self._lock:
            if backend is self._failing_backend:
                self._failing_backend = None
                self._failed_renders = 0

    def restart_backends(self) -> None:
        """Drop the cached backends, so the next sentence builds fresh ones.

        A backend whose service died (Pipecat marks it unusable) stays dead
        for as long as it is cached. One the caller supplied is dropped from the
        cache but not closed: it is the caller's, and it speaks again.

        The fresh set is warmed again by the next `warm_up`: its models are
        other models."""
        with self._lock:
            self._is_restart_pending = False
            if self._is_closed:
                return
            self._backends = None
            owned, self._owned_backends = self._owned_backends, []
            self._failing_backend = None
            self._failed_renders = 0
            # A warm-up still running is warming what `_backends` no longer
            # holds: its completion must not mark the fresh set warm, and the
            # set it leaves behind is a new generation's to warm.
            self._warm_up_generation += 1
            self._is_warming_up = False
            self._is_warmed_up = False
        for backend in owned:
            backend.close()

    def _get_backends(self) -> list[AnySpeechBackend]:
        """Return this speaker's cached backends."""
        with self._building:
            return self._get_backends_unlocked()

    def _get_backends_unlocked(self) -> list[AnySpeechBackend]:
        with self._lock:
            is_restart_pending = self._is_restart_pending
        if is_restart_pending:
            self.restart_backends()
        if self._backends is None:
            backends = self._build_backends()
            with self._lock:
                self._backends = backends
                self._owned_backends = [
                    backend
                    for backend in backends
                    if backend is not self._config.backend
                ]
        return self._backends

    def _build_backends(self) -> list[AnySpeechBackend]:
        """The backends that speak a sentence, the configured one first."""
        config = self._config
        requested = get_speech_backend(config.backend or "auto", config)
        backends = [requested]
        if self._should_use_the_local_engine(requested):
            # Resolve the local fallback without the configured voice.
            local = get_speech_backend("auto", replace(config, voice=""))
            if local.name != requested.name:
                backends.append(local)
        return backends

    def _should_use_the_local_engine(self, backend: AnySpeechBackend) -> bool:
        """Whether a sentence *backend* cannot make may be read by the local
        engine instead.

        A local voice rendered here has no second voice: `say` would be somebody
        else reading the reply, so where zrb can play it, a failure is reported
        rather than spoken in another voice. Where zrb cannot play it at all,
        the local engine is the only way the reply is heard."""
        if not self._can_play_in_process():
            return True
        return not (backend.is_local and backend.needs_zrb_playback)

    def _prepare_queue(self) -> None:
        """Make each queued text's audio, handing it to the player thread."""
        while (entry := self._queue.get()) is not None:
            item, is_stale, generation, voice = entry
            token = current_speech_voice.set(voice)
            try:
                text = item() if callable(item) else item
                utterance = self._prepare(text, is_stale)
            except Exception as exc:
                logger.warning(f"Speech failed: {exc}")
                continue
            finally:
                current_speech_voice.reset(token)
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
                except FileLockTimeout:
                    logger.warning(
                        "Speech dropped: another session held the audio device"
                    )
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
        # But do wait for the stream playing to be let go of: a process ending
        # now would otherwise stop it a second time from PortAudio's exit
        # handler.
        wait_for_streams_to_close(_STREAM_CLOSE_WAIT_SECONDS)

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
        finally:
            wait_for_streams_to_close(_STREAM_CLOSE_WAIT_SECONDS)

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
        """Let the backends go for good; a closed speaker builds no more.

        Only the ones zrb built are closed. A backend the caller supplied is the
        caller's to close: closing it left every later session of a chat reusing
        a dead one, and each of its sentences falling back to another voice."""
        with self._lock:
            self._backends = []
            owned, self._owned_backends = self._owned_backends, []
        for backend in owned:
            backend.close()


def _resolve_player(player: str | None) -> str:
    mode = (player or "auto").strip().lower()
    if mode in _PLAYERS:
        return mode
    logger.warning(f"Unknown speech player {player!r}: use auto or command; auto it is")
    return "auto"


def play(utterance: Utterance, config: SpeechConfig) -> None:
    """Play *utterance* while holding the resolved audio lock.

    Raises `FileLockTimeout` when another session holds the lock past
    *config.lock_timeout*, and whatever the utterance's player raises.
    """
    with hold_file_lock(
        config.lock_file or CFG.LLM_SPEECH_LOCK_FILE, timeout=config.lock_timeout
    ):
        _set_playing(+1)
        try:
            utterance.play(config.player_timeout or None)
        finally:
            _set_playing(-1)


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
