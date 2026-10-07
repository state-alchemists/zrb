"""`enable_dictation`: speech-to-text input for chat sessions.

``ptt`` mode: the dictation command starts recording, and the same command
or a pause stops it; the transcript lands in the input box to edit and send.
``hands_free`` mode: the microphone stays open and each utterance becomes a
turn, or answers the approval or question being asked. The hands-free
command switches between the two.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.builtin import get_dictation_backend
from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.listen import MicState, Utterance, import_audio, listen
from zrb.llm.dictation.words import (
    count_words,
    is_answer,
    is_said_alone,
    is_transcriber_guess,
    split_phrases,
    strip_wake_word,
    to_answer,
)
from zrb.llm.input_source import DICTATION_INPUT
from zrb.llm.speech.feature import interrupt_speech, pause_speech, resume_speech
from zrb.llm.ui.trigger import TriggerReply
from zrb.llm.util.feature_config import (
    current_session_key,
    get_session_ui,
    replace_feature_sessions,
    replace_registration,
)
from zrb.llm.util.teardown import close_quietly
from zrb.util.cli.style import stylize_muted

if TYPE_CHECKING:
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.ui.any_ui import AnyUI
    from zrb.llm.ui.base.ui import BaseUI

logger = logging.getLogger(__name__)

HANDS_FREE = "hands_free"
# Badge emoji are all wide by default (Emoji_Presentation). One made an emoji
# by a variation selector (U+FE0F after the writing hand or the studio
# microphone) is drawn one column wide by many terminals but counted as two
# by prompt_toolkit, so it overlaps the next letter ("trenscribing").
BADGE_KEY = "dictation"
_LISTENING = "🎤 listening"
_MIC_STATE_BADGES = {
    MicState.HEARING: "👂 hearing you…",
    MicState.PAUSED: "🔇 mic paused while speaking",
}
_TRANSCRIBING = "📝 transcribing…"
_INTERRUPTED = "✋ interrupted · go on…"
_PAUSED = "✋ paused · listening…"
_MAX_QUOTED_CHARS = 40


def enable_dictation(
    chat: "LLMChatTask", config: DictationConfig | None = None
) -> None:
    """Add the dictation commands and the hands-free listener to *chat*'s
    sessions; empty command lists leave the commands out. The microphone opens
    only for a recording, or while hands-free is on. Calling it again replaces
    the earlier call."""
    sessions = replace_feature_sessions(
        chat,
        "dictation",
        lambda: DictationSession((config or DictationConfig()).resolve()),
        lambda session: session.close(),
    )

    def create_commands() -> "list[AnyCustomCommand]":
        return sessions.get().create_commands()

    async def hands_free() -> AsyncGenerator[TriggerReply, None]:
        async with aclosing(sessions.get().listen_hands_free()) as listener:
            async for reply in listener:
                yield reply

    replace_registration(
        chat,
        "dictation",
        [("append_custom_command", create_commands), ("append_trigger", hands_free)],
    )


class DictationSession:
    """Push-to-talk and hands-free state for one resolved *config*."""

    def __init__(self, config: DictationConfig) -> None:
        self._config = config
        self._backend: AnyDictationBackend | None = None
        # Set by `close`, which is the session's own end: nothing new is built into
        # it after that, and nothing is transcribed for it.
        self._is_closed = False
        # Letting a backend go is asynchronous, so `close` schedules it rather
        # than awaiting it; this is the task, kept so nothing collects it early.
        self._backend_close: asyncio.Task[None] | None = None
        self._stop_recording: asyncio.Event | None = None
        # Set when hands-free is switched off, so a transcription already under
        # way can be dropped instead of submitted after the user said stop.
        self._hands_free_off = asyncio.Event()
        self._wake_words = split_phrases(config.wake_words or [])
        self._approve_words = split_phrases(config.approve_words or [])
        self._deny_words = split_phrases(config.deny_words or [])
        self._stop_words = split_phrases(config.stop_words or [])
        self._polite_words = config.polite_words
        # The UI hands-free was last switched on from, for when no UI is bound
        # to the session.
        self._ui: "AnyUI | None" = None
        # The badge shown while the mic is listening, which says what the last
        # utterance came to and, when it is not the default, whose ears it went
        # through.
        self._resting_badge = self._listening_badge()
        # The chat session this belongs to, whose speech a barge-in silences.
        self._session_key = current_session_key()
        # zrb's voice is held because the user may be talking over it, until
        # what they said is known to be words (stop) or not (resume).
        self._is_paused_by_barge_in = False
        # The resting badge a barge-in replaced, back once zrb resumes.
        self._badge_before_pause = self._resting_badge
        # A wake word said alone arms the utterances started before this.
        self._armed_until = 0.0
        self.is_hands_free = (config.mode or "").strip().lower() == HANDS_FREE

    @property
    def backend(self) -> AnyDictationBackend:
        """The configured backend, built on first use so a misconfigured one
        fails only a session that uses dictation."""
        return self._get_backend()

    @backend.setter
    def backend(self, backend: AnyDictationBackend) -> None:
        self._backend = backend

    def _get_backend(self) -> AnyDictationBackend:
        if self._backend is None:
            if self._is_closed:
                # A recording or a transcription that outlived the session it was
                # started for: building a backend here would build one nothing
                # will ever let go.
                raise RuntimeError(
                    "this dictation session has ended, so it builds no backend and "
                    "transcribes nothing more"
                )
            self._backend = get_dictation_backend(
                self._config.backend or "vosk", self._config
            )
        return self._backend

    @property
    def is_recording(self) -> bool:
        return self._stop_recording is not None

    def close(self) -> None:
        """Switch hands-free off, release a recording in progress, and let the
        backend go."""
        self._is_closed = True
        self._release_barge_in()
        self.is_hands_free = False
        self._hands_free_off.set()
        if self._stop_recording is not None:
            self._stop_recording.set()
        self._close_backend()
        self._show(None)

    def _close_backend(self) -> None:
        """Let the backend go, without this teardown waiting for it.

        A backend may hold a model or a running pipeline — a Pipecat service is
        both — and letting one go is asynchronous where this teardown is not. A
        failure is reported by nobody, which is what `close_quietly` is for, and
        the task is kept so it is not collected before it has run.

        Where it runs is the backend's answer, not this teardown's. A Pipecat
        pipeline's worker is a task on the loop that started it, and awaiting it
        from another loop raises the cross-loop error `close_quietly` swallows —
        a teardown reporting a closed backend while the worker, the model and the
        pipeline keep running. A loop that has stopped altogether is the one case
        with no close left in it: the backend is asked to release what it holds
        instead, so the model behind its pipeline can be collected rather than
        stay alive behind the reference this teardown is about to drop. A loop can
        stop in the window between being asked whether it is running and being
        handed the close, which is the same case arriving one line later.
        """
        backend, self._backend = self._backend, None
        if backend is None:
            return
        try:
            here = asyncio.get_running_loop()
        except RuntimeError:
            here = None
        owner = backend.owner_loop
        if owner is not None and owner is not here:
            if not owner.is_running():
                self._release_backend(backend)
                return
            try:
                owner.call_soon_threadsafe(
                    lambda: self._close_backend_on(owner, backend)
                )
            except RuntimeError:
                # The loop stopped between the question above and this call, so it
                # takes no callback now — the case that question was asked about,
                # one line later.
                self._release_backend(backend)
            return
        if here is not None:
            self._close_backend_on(here, backend)
            return
        # Nothing this backend holds is bound to a loop, so its close runs to
        # completion on one of its own: a coroutine left unscheduled would only
        # warn once it was collected — with the backend, and whatever model or
        # pipeline it was holding, still alive.
        asyncio.run(close_quietly(backend.aclose, "the dictation backend"))

    def _release_backend(self, backend: AnyDictationBackend) -> None:
        """Let a backend go where no loop is left that will run its close.

        A loop that has stopped takes no callback, so the close has nowhere to run
        and the backend keeps what it was built with — for a Pipecat service, a
        model behind a pipeline and a worker. Dropping that is what lets them be
        collected, and the teardown names the part it could not do.
        """
        backend.release()
        logger.warning(
            "Could not stop the dictation backend: the loop it was built on is not "
            "running, so its worker cannot be cancelled; the backend released what "
            "it held"
        )

    def _close_backend_on(
        self, loop: asyncio.AbstractEventLoop, backend: AnyDictationBackend
    ) -> None:
        """Close *backend* as a task on *loop*, kept so nothing collects it early."""
        self._backend_close = loop.create_task(
            close_quietly(backend.aclose, "the dictation backend")
        )

    def create_commands(self) -> "list[AnyCustomCommand]":
        push_to_talk: "list[AnyCustomCommand]" = [
            ActionCommand(
                command,
                self.toggle_recording,
                description="Start or stop a voice recording",
                can_run_while_thinking=True,
            )
            for command in self._config.commands or []
        ]
        hands_free = [
            ActionCommand(
                command,
                self.toggle_hands_free,
                description="Switch hands-free voice input on or off",
                can_run_while_thinking=True,
            )
            for command in self._config.hands_free_commands or []
        ]
        return push_to_talk + hands_free

    def toggle_recording(self, kwargs: dict[str, str], ui: "BaseUI | None"):
        """Stop the recording in progress, else start one."""
        if self._stop_recording is not None:
            self._stop_recording.set()
            return "🎤 Stopping..."
        if ui is None:
            return "🎤 Recording needs an interactive chat session."
        if self.is_hands_free:
            commands = ", ".join(self._config.hands_free_commands or [])
            return f"🎤 Hands-free is on; switch it off first ({commands})."
        try:
            self._get_backend()
        except ValueError as e:
            return f"🎤 {e}"
        stop = asyncio.Event()
        self._stop_recording = stop
        recording = asyncio.ensure_future(self._record_into(ui, stop))
        # A done callback, not a `finally`: a task cancelled before its first
        # step never enters the coroutine.
        recording.add_done_callback(lambda _: self._release_recording(stop))
        return recording

    def _release_recording(self, stop: asyncio.Event) -> None:
        if self._stop_recording is stop:
            self._stop_recording = None

    def toggle_hands_free(self, kwargs: dict[str, str], ui: "BaseUI | None") -> str:
        if not self.is_hands_free:
            try:
                import_audio()
                self._get_backend()
            except (RuntimeError, ValueError) as e:
                return f"🎤 {e}"
            if ui is not None:
                self._ui = ui
        self.is_hands_free = not self.is_hands_free
        if self.is_hands_free:
            self._hands_free_off.clear()
        else:
            self._hands_free_off.set()
            self._release_barge_in()
            self._show(None)
        if self._stop_recording is not None:
            self._stop_recording.set()
        return f"🎤 Hands-free {'on' if self.is_hands_free else 'off'}"

    async def _record_into(self, ui: "BaseUI", stop: asyncio.Event) -> str:
        # Taken once, and this one backend is what records and what transcribes:
        # a session that ends in the middle of a recording must be the end of the
        # backend that was started for it, not the start of another.
        backend = self.backend
        await backend.prepare(_to_output(ui))
        commands = ", ".join(self._config.commands or [])
        try:
            self._show(f"🔴 recording… ({commands} or a pause to stop)", ui)
            audio = await self._record_one(stop)
            self._show(_TRANSCRIBING, ui)
            text = await self._transcribe_recording(backend, audio)
        finally:
            self._show(None, ui)
        if not text:
            return "🎤 Heard nothing."
        ui.insert_input_text(text)
        return "🎤 Transcribed: edit it or press Enter to send."

    async def _transcribe_recording(
        self, backend: AnyDictationBackend, audio: bytes
    ) -> str:
        """What *audio* came to, or ``""`` when there is nothing to transcribe.

        Nothing is waiting for a transcript once the session is over — the input
        box it would be edited in is gone — and the backend the teardown let go
        must not be asked to start itself up again for one.
        """
        if not audio or self._is_closed:
            return ""
        return (await backend.transcribe(audio)).strip()

    async def _record_one(self, stop: asyncio.Event) -> bytes:
        def should_listen() -> bool:
            return not stop.is_set()

        # aclosing, or the `with stream` inside `listen` waits on generator
        # finalization to close the microphone.
        async with aclosing(
            listen(self._config, should_listen, keep_partial=True)
        ) as mic:
            async for utterance in mic:
                return utterance.audio
            return b""

    async def listen_hands_free(self) -> AsyncGenerator[TriggerReply, None]:
        """Yield one reply per utterance while hands-free is on, for the life
        of the session. Progress and failures go to the UI hands-free was last
        switched on from, else to the log."""
        while True:
            while not self.is_hands_free:
                await asyncio.sleep(0.2)
            try:
                await self.backend.prepare(self._report)
                self._warn_without_wake_words()
                self._rest(self._listening_badge())
                async with aclosing(self._replies()) as replies:
                    async for reply in replies:
                        yield reply
            except Exception as exc:
                # Stop rather than retry a broken microphone forever.
                self._release_barge_in()
                self._report(f"Hands-free dictation stopped: {exc}")
                self.is_hands_free = False
            finally:
                self._show(None)

    async def _replies(self) -> AsyncGenerator[TriggerReply, None]:
        self._armed_until = 0.0
        # aclosing so switching hands-free off closes the microphone as soon as
        # the utterance in flight is dropped, not at finalization.
        async with aclosing(self._listen()) as mic:
            async for utterance in mic:
                self._show(_TRANSCRIBING)
                try:
                    text = await self._transcribe_or_drop(utterance)
                except Exception as exc:
                    self._release_barge_in()
                    self._rest("❗ transcription failed · listening")
                    self._report(f"Hands-free transcription failed: {exc}")
                    continue
                if text is None:
                    self._release_barge_in()
                    return
                command = await self._to_command(utterance, text)
                if command is not None:
                    yield self._to_reply(command, utterance)

    async def _listen(self) -> AsyncGenerator[Utterance, None]:
        """`listen` while hands-free holds.

        The microphone closes when hands-free stops; the caller must close the
        generator (or the microphone stays open until it is finalized).
        """
        # Taken once, for the same reason a recording takes one: a stream is made
        # per utterance, and a session that ends mid-utterance must not have a new
        # backend built for the microphone it still has.
        backend = self.backend
        async with aclosing(
            listen(
                self._config,
                lambda: self.is_hands_free,
                on_state=self._show_mic_state,
                on_barge_in=self._handle_barge_in,
                create_stream=backend.create_stream,
                on_partial=self._show_partial,
                on_barge_in_dropped=self._release_barge_in,
            )
        ) as mic:
            async for utterance in mic:
                yield utterance

    async def _to_command(self, utterance: Utterance, text: str) -> str | None:
        """What *utterance*, transcribed as *text*, asks zrb, or ``None``
        when there is nothing to send; the badge says which."""
        why_not = self._get_why_not_the_user(text)
        if why_not:
            # Not the user's words: zrb carries on, and nothing is sent.
            self._release_barge_in()
            self._rest(f"🎤 ignored {_quote(text)} ({why_not})")
            return None
        command = self._get_command(utterance, text)
        if command and self._is_interrupting(utterance):
            # Asked before the minimum word count, not after it: a one-word stop
            # the word lists do not know ("berhenti") is exactly what the judge
            # is for, and the count would drop it before the judge ever saw it.
            # A stop cancels the turn here; anything else leaves the count
            # standing, and an ordinary short utterance is never asked at all.
            if not await self._should_send_barge_in(utterance, command):
                return None
        if command:
            why_short = self._get_why_too_short(utterance, command)
            if why_short:
                self._release_barge_in()
                self._rest(f"🎤 ignored {_quote(command)} ({why_short})")
                return None
        self._settle_barge_in(utterance, command is not None)
        if not command:
            self._rest_without_command(utterance, text, command)
            return None
        self._armed_until = 0.0
        self._rest(f"🎤 heard {_quote(command)} · listening")
        return command

    def _get_why_not_the_user(self, text: str) -> str:
        """Why hands-free *text* is not the user's words, or ``""``. A stop
        word or yes/no is never set aside ("no no" is meant), and neither is
        anything with a wake word at the front: one phrase said twice reads as
        a transcriber guessing at noise, but saying stop twice is what someone
        does when the first one went unheard."""
        if not text or self._is_answer_or_stop(text):
            return ""
        if is_transcriber_guess(text) and not self._is_wake_worded(text):
            return "the transcriber guessing at noise"
        return ""

    def _is_wake_worded(self, text: str) -> bool:
        """Whether *text* starts with a wake word; false with none set."""
        return (
            bool(self._wake_words)
            and strip_wake_word(text, self._wake_words) is not None
        )

    def _is_answer_or_stop(self, text: str) -> bool:
        """Whether *text* is only a stop, or only a yes or a no.

        A stop is one only when it is said alone (`_get_barge_in_intent`); an
        approval and a denial carry a polite word, as `_to_reply` reads them,
        so "yes please" and "no thanks" count as answers here rather than being
        dropped by the minimum word count.
        """
        if is_said_alone(text, self._stop_words):
            return True
        return is_answer(
            text, self._approve_words, self._deny_words, self._polite_words
        )

    def _get_why_too_short(self, utterance: Utterance, command: str) -> str:
        """Why *command* has too few words to reach the model, or ``""``.

        `barge_in_min_words` for one interrupting zrb, whose voice and noise
        come through as a word or two; `min_words` for an ordinary hands-free
        utterance, which is how a public place is made to need more than a
        stray word. A stop word, a yes/no, or an answer to the prompt being
        asked always counts — and the UI is consulted only for words that
        would otherwise be dropped, so an ordinary utterance never asks it
        anything."""
        if self._is_answer_or_stop(command):
            return ""
        if self._is_interrupting(utterance):
            minimum, why = self._config.barge_in_min_words, "too few words to interrupt"
        else:
            minimum, why = self._config.min_words, "too few words"
        if count_words(command) >= (minimum or 0):
            return ""
        ui = get_session_ui() or self._ui
        if ui is not None and ui.is_waiting_for_answer:
            return ""
        return why

    def _get_command(self, utterance: Utterance, text: str) -> str | None:
        """*text* past its wake word; ``""`` for the wake word alone, and
        ``None`` for no words or none meant for zrb."""
        if not text:
            return None
        command = strip_wake_word(text, self._wake_words)
        # Against when the utterance was spoken, not when transcription
        # finished: transcription alone can take seconds.
        if command is None and utterance.started_at < self._armed_until:
            command = text
        return command

    def _rest_without_command(
        self, utterance: Utterance, text: str, command: str | None
    ) -> None:
        if not text:
            self._rest("🎤 didn't catch that · listening")
        elif command is None:
            self._rest(f"🎤 ignored {_quote(text)} (no wake word)")
        else:
            # The wake word alone: people pause after it.
            self._armed_until = utterance.ended_at + (self._config.wake_window or 0)
            self._rest("🎤 go ahead…")

    def _to_reply(self, command: str, utterance: Utterance) -> TriggerReply:
        reply = TriggerReply(
            command,
            approval=to_answer(
                command, self._approve_words, self._deny_words, self._polite_words
            ),
            started_at=utterance.started_at,
        )
        object.__setattr__(reply, "source", DICTATION_INPUT)
        return reply

    def _handle_barge_in(self) -> None:
        """The user may be talking over zrb: hold its voice at once, and let
        the words decide whether it stays held.

        Held on loudness, before anything is known: the microphone has heard
        speech over zrb, and being talked over is worse than a pause that
        turns out to be zrb's own voice — `_release_barge_in` gives that back
        a moment later. Waiting for the words instead would leave zrb talking
        through the whole sentence that interrupted it."""
        if not self._is_paused_by_barge_in:
            self._badge_before_pause = self._resting_badge
        self._is_paused_by_barge_in = True
        pause_speech(self._session_key)
        self._rest(_PAUSED)

    def _settle_barge_in(self, utterance: Utterance, is_meant_for_zrb: bool) -> None:
        """For *utterance* said over zrb: stop zrb for words meant for it
        (with wake words: starting with one); carry on after anything else
        (a cough, leftover echo) — which is where a hold taken on loudness
        alone is given back. Words too brief to have held zrb (a crisp "stop"
        is shorter than ``barge_in_min_speech``) stop it too."""
        if not utterance.is_over_speech:
            return
        if not is_meant_for_zrb:
            self._release_barge_in()
        elif self._is_paused_by_barge_in or not utterance.is_barge_in:
            self._stop_speech()

    def _confirm_barge_in(self) -> None:
        """A wake word heard while zrb is still speaking: the hold taken on
        loudness was the user's, so it becomes a stop."""
        if self._is_paused_by_barge_in:
            self._stop_speech()

    def _stop_speech(self) -> None:
        self._is_paused_by_barge_in = False
        interrupt_speech(self._session_key)
        self._rest(_INTERRUPTED)

    def _release_barge_in(self) -> None:
        """zrb carries on: resume its voice and the badge it paused."""
        if self._is_paused_by_barge_in:
            self._is_paused_by_barge_in = False
            resume_speech(self._session_key)
            self._rest(self._badge_before_pause)

    def _is_interrupting(self, utterance: Utterance) -> bool:
        """Whether *utterance* talks over zrb: over its voice, or, with
        barge-in on, while a turn runs and zrb is not yet speaking."""
        if utterance.is_over_speech:
            return True
        if not self._config.is_barge_in_enabled:
            return False
        ui = get_session_ui() or self._ui
        return ui is not None and ui.is_thinking

    async def _should_send_barge_in(self, utterance: Utterance, command: str) -> bool:
        """Act on what the user said over zrb, and say whether it still goes on
        to be a turn or an answer.

        A stop — a word-list phrase said alone, or what the judge reads as one —
        stops zrb speaking and cancels the turn, and is sent nowhere. An answer
        to the prompt being asked is left alone: "no" there denies a tool call,
        not the turn."""
        ui = get_session_ui() or self._ui
        if ui is None or ui.is_waiting_for_answer:
            return True
        if await self._get_barge_in_intent(command) == "stop":
            self._settle_barge_in(utterance, True)
            ui.cancel_current_turn("barge_in")
            self._rest("✋ stopped · listening")
            return False
        return True

    async def _get_barge_in_intent(self, command: str) -> str:
        """What *command*, said over zrb, asks of it: ``"stop"`` or ``"ask"``.

        The word lists answer first, for free, and stand when the judge is off
        or could not answer. What they miss — a stop word carrying an
        expletive, the same stop said twice, a stop in another language — is
        what the small model is for, and it is asked only when they miss it."""
        if is_said_alone(command, self._stop_words):
            return "stop"
        if not self._config.interrupt_judge_enabled:
            return "ask"
        # lazy: heavy transitive (pydantic_ai) via zrb.llm.dictation.interrupt_judge
        from zrb.llm.dictation.interrupt_judge import judge_barge_in

        verdict = await judge_barge_in(
            command, self._config.interrupt_judge_model or None
        )
        return verdict.intent if verdict is not None else "ask"

    def _show_partial(self, partial: str) -> None:
        """Show the end of what is being heard, while it is said. With wake
        words, words heard over zrb that start with one stop it without
        waiting for the utterance to end. Without, the transcript decides:
        a streaming recognizer guesses a word ("the") for a cough, and zrb
        is already paused, so waiting costs nothing."""
        if not partial:
            return
        self._show(f"👂 …{partial[-_MAX_QUOTED_CHARS:]}")
        if self._wake_words and self._is_paused_by_barge_in:
            if strip_wake_word(partial, self._wake_words) is not None:
                self._confirm_barge_in()

    def _show_mic_state(self, state: MicState) -> None:
        self._show(_MIC_STATE_BADGES.get(state, self._resting_badge))

    def _listening_badge(self) -> str:
        """What the badge says while the microphone is open.

        A service the user named is shown; the default one is not, so a session
        on vosk reads exactly as it did before there was a choice. This is where
        that choice becomes visible: `prepare` announces the load into the
        transcript before the UI paints, and that line is not what a user can
        rely on to know whether naming a service took effect.
        """
        service = self._named_service()
        if not service:
            return _LISTENING
        return f"{_LISTENING} · {service}"

    def _named_service(self) -> str:
        """The service `LLM_DICTATION_BACKEND` names, or ``""`` when it is the
        default one — including when a session was handed a backend object
        built in code, which has no name of its own to show."""
        backend = self._config.backend
        if not isinstance(backend, str):
            return ""
        name = backend.strip().lower()
        return "" if name in ("", "vosk") else name

    def _rest(self, badge: str) -> None:
        """Show *badge*, and come back to it whenever the mic is listening."""
        self._resting_badge = badge
        self._show(badge)

    def _show(self, badge: str | None, ui: "AnyUI | None" = None) -> None:
        target = get_session_ui() or ui or self._ui
        if target is not None:
            target.set_status_badge(BADGE_KEY, badge)

    def _report(self, message: str) -> None:
        """Say *message* on the session's UI, else log it."""
        ui = get_session_ui() or self._ui
        if ui is None:
            logger.warning(message)
            return
        _to_output(ui)(message)

    def _warn_without_wake_words(self) -> None:
        """Say, whenever the microphone opens, that without a wake word
        everything heard is taken for the user — what a noisy place makes
        obvious and a quiet one hides."""
        if self._wake_words:
            return
        self._report(
            "Hands-free takes everything it hears: set "
            f"{CFG.ENV_PREFIX}_LLM_DICTATION_WAKE_WORDS so only speech "
            "starting with a wake word counts, or a conversation in the room "
            "becomes a turn."
        )

    async def _transcribe_or_drop(self, utterance: Utterance) -> str | None:
        """*utterance*'s transcript, finished by its stream when it has one,
        or ``None`` when hands-free was switched off while it was being
        transcribed — the user said stop, so that utterance is theirs, not the
        model's."""
        if self._is_closed:
            # The session is over, so the utterance goes the way of one that was
            # dropped, and the backend the teardown let go is left alone.
            return None
        # Taken once, for the same reason the other operations take one.
        backend = self.backend
        if utterance.stream is not None:
            coroutine = utterance.stream.finish()
        else:
            coroutine = backend.transcribe_speech(utterance.audio)
        transcribing = asyncio.ensure_future(coroutine)
        switched_off = asyncio.ensure_future(self._hands_free_off.wait())
        is_finished = False
        try:
            await asyncio.wait(
                {transcribing, switched_off}, return_when=asyncio.FIRST_COMPLETED
            )
            if not transcribing.done():
                return None
            text = (await transcribing).strip()
            is_finished = True
            return text
        finally:
            for task in (transcribing, switched_off):
                if not task.done():
                    task.cancel()
            # A stream that did not finish (hands-free switched off, `finish`
            # failed, this task cancelled) is abandoned, and an abandoned
            # stream is closed: it may hold a connection or a decoder.
            if utterance.stream is not None and not is_finished:
                await close_quietly(utterance.stream.close, "a transcription stream")


def _quote(text: str) -> str:
    """*text* on one line, cut to fit a status bar."""
    line = " ".join(text.split())
    if len(line) > _MAX_QUOTED_CHARS:
        line = line[: _MAX_QUOTED_CHARS - 1].rstrip() + "…"
    return f'"{line}"'


def _to_output(ui: "AnyUI") -> Callable[[str], None]:
    return lambda message: ui.append_to_output(stylize_muted(f"\n  🎤 {message}\n"))
