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

from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.builtin import get_dictation_backend
from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.echo.builtin import get_echo_canceller
from zrb.llm.dictation.echo.cancellation import EchoCancellation
from zrb.llm.dictation.listen import MicState, Utterance, import_audio, listen
from zrb.llm.dictation.words import split_phrases, strip_wake_word, to_answer
from zrb.llm.speech.feature import interrupt_speech, pause_speech, resume_speech
from zrb.llm.ui.trigger import TriggerReply
from zrb.llm.util.feature_config import (
    current_session_key,
    get_session_ui,
    replace_feature_sessions,
    replace_registration,
)
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
# How long a cancelled turn may take to unwind before what the user said
# is sent anyway.
_TURN_END_TIMEOUT = 5.0
_TURN_END_POLL = 0.05
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
        self._stop_recording: asyncio.Event | None = None
        # Set when hands-free is switched off, so a transcription already under
        # way can be dropped instead of submitted after the user said stop.
        self._hands_free_off = asyncio.Event()
        self._wake_words = split_phrases(config.wake_words or [])
        self._approve_words = split_phrases(config.approve_words or [])
        self._deny_words = split_phrases(config.deny_words or [])
        # The UI hands-free was last switched on from, for when no UI is bound
        # to the session.
        self._ui: "AnyUI | None" = None
        # The badge shown while the mic is listening, which says what the last
        # utterance came to.
        self._resting_badge = _LISTENING
        # The chat session this belongs to, whose speech a barge-in silences.
        self._session_key = current_session_key()
        # zrb's voice is held because the user may be talking over it, until
        # what they said is known to be words (stop) or not (resume).
        self._is_paused_by_barge_in = False
        # One per session: it keeps what it learned of the room.
        self._echo: "EchoCancellation | None" = None
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
            self._backend = get_dictation_backend(
                self._config.backend or "vosk", self._config
            )
        return self._backend

    @property
    def is_recording(self) -> bool:
        return self._stop_recording is not None

    def close(self) -> None:
        """Switch hands-free off and release a recording in progress."""
        self._release_barge_in()
        self.is_hands_free = False
        self._hands_free_off.set()
        if self._stop_recording is not None:
            self._stop_recording.set()
        self._show(None)

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
            self._show(None)
        if self._stop_recording is not None:
            self._stop_recording.set()
        return f"🎤 Hands-free {'on' if self.is_hands_free else 'off'}"

    async def _record_into(self, ui: "BaseUI", stop: asyncio.Event) -> str:
        await self.backend.prepare(_to_output(ui))
        commands = ", ".join(self._config.commands or [])
        try:
            self._show(f"🔴 recording… ({commands} or a pause to stop)", ui)
            audio = await self._record_one(stop)
            self._show(_TRANSCRIBING, ui)
            text = (await self.backend.transcribe(audio)).strip() if audio else ""
        finally:
            self._show(None, ui)
        if not text:
            return "🎤 Heard nothing."
        ui.insert_input_text(text)
        return "🎤 Transcribed: edit it or press Enter to send."

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
                self._rest(_LISTENING)
                async with aclosing(self._replies()) as replies:
                    async for reply in replies:
                        yield reply
            except Exception as exc:
                # Stop rather than retry a broken microphone forever.
                self._report(f"Hands-free dictation stopped: {exc}")
                self.is_hands_free = False
            finally:
                self._show(None)

    async def _replies(self) -> AsyncGenerator[TriggerReply, None]:
        armed_until = 0.0
        # aclosing so switching hands-free off closes the microphone as soon as
        # the utterance in flight is dropped, not at finalization.
        mic_listen = listen(
            self._config,
            lambda: self.is_hands_free,
            on_state=self._show_mic_state,
            on_barge_in=self._handle_barge_in,
            create_stream=self.backend.create_stream,
            on_partial=self._show_partial,
            echo=self._get_echo(),
            on_barge_in_dropped=self._release_barge_in,
        )
        async with aclosing(mic_listen) as mic:
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
                command = strip_wake_word(text, self._wake_words) if text else None
                # Against when the utterance was spoken, not when transcription
                # finished: transcription alone can take seconds.
                if command is None and text and utterance.started_at < armed_until:
                    command = text
                if utterance.is_barge_in:
                    self._settle_barge_in(command is not None)
                if not text:
                    self._rest("🎤 didn't catch that · listening")
                    continue
                if command is None:
                    self._rest(f"🎤 ignored {_quote(text)} (no wake word)")
                    continue
                if not command:
                    # The wake word alone: people pause after it.
                    armed_until = utterance.ended_at + (self._config.wake_window or 0)
                    self._rest("🎤 go ahead…")
                    continue
                armed_until = 0.0
                if utterance.is_barge_in and not await self._should_send_barge_in(
                    command
                ):
                    continue
                self._rest(f"🎤 heard {_quote(command)} · listening")
                yield TriggerReply(
                    command,
                    approval=to_answer(command, self._approve_words, self._deny_words),
                    started_at=utterance.started_at,
                )

    def _get_echo(self) -> "EchoCancellation | None":
        """The session's echo cancellation, built on first use with barge-in
        on; it keeps what it learned of the room across microphone reopens."""
        if (self._config.barge_in or "off").strip().lower() != "on":
            return None
        if self._echo is None:
            canceller = get_echo_canceller(self._config.echo_canceller or "numpy")
            self._echo = EchoCancellation(
                canceller, threshold=self._config.threshold or 0.01
            )
        return self._echo

    def _handle_barge_in(self) -> None:
        """The user may be talking over zrb: hold its voice at once, until
        what they said turns out to be words or not."""
        self._is_paused_by_barge_in = True
        pause_speech(self._session_key)
        self._rest(_PAUSED)

    def _settle_barge_in(self, is_meant_for_zrb: bool) -> None:
        """Stop zrb for words meant for it (with wake words: starting with
        one); carry on after anything else (a cough, leftover echo)."""
        if is_meant_for_zrb:
            self._confirm_barge_in()
        else:
            self._release_barge_in()

    def _confirm_barge_in(self) -> None:
        if self._is_paused_by_barge_in:
            self._is_paused_by_barge_in = False
            interrupt_speech(self._session_key)
            self._rest(_INTERRUPTED)

    def _release_barge_in(self) -> None:
        if self._is_paused_by_barge_in:
            self._is_paused_by_barge_in = False
            resume_speech(self._session_key)

    async def _should_send_barge_in(self, command: str) -> bool:
        """Act on what the user said over zrb, and say whether it still goes
        on to be a turn or an answer. A deny word alone stops the turn and is sent
        nowhere; with ``barge_in_action`` ``cancel``, anything else stops the
        turn and starts a new one. An answer to the prompt being asked is
        left alone: "no" there denies a tool call, not the turn."""
        ui = get_session_ui() or self._ui
        if ui is None or getattr(ui, "is_waiting_for_answer", False):
            return True
        if to_answer(command, [], self._deny_words) == "no":
            ui.cancel_current_turn("barge_in")
            self._rest("✋ stopped · listening")
            return False
        action = (self._config.barge_in_action or "steer").strip().lower()
        if action == "cancel" and ui.is_thinking:
            ui.cancel_current_turn("barge_in")
            await _wait_for_turn_end(ui)
        return True

    def _show_partial(self, partial: str) -> None:
        """Show the end of what is being heard, while it is said; words
        heard over zrb stop it without waiting for the utterance to end."""
        if not partial:
            return
        self._show(f"👂 …{partial[-_MAX_QUOTED_CHARS:]}")
        if self._is_paused_by_barge_in and (
            strip_wake_word(partial, self._wake_words) is not None
        ):
            self._confirm_barge_in()

    def _show_mic_state(self, state: MicState) -> None:
        self._show(_MIC_STATE_BADGES.get(state, self._resting_badge))

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

    async def _transcribe_or_drop(self, utterance: Utterance) -> str | None:
        """*utterance*'s transcript, finished by its stream when it has one,
        or ``None`` when hands-free was switched off while it was being
        transcribed — the user said stop, so that utterance is theirs, not the
        model's."""
        if utterance.stream is not None:
            coroutine = utterance.stream.finish()
        else:
            coroutine = self.backend.transcribe(utterance.audio)
        transcribing = asyncio.ensure_future(coroutine)
        switched_off = asyncio.ensure_future(self._hands_free_off.wait())
        try:
            await asyncio.wait(
                {transcribing, switched_off}, return_when=asyncio.FIRST_COMPLETED
            )
            if not transcribing.done():
                return None
            return (await transcribing).strip()
        finally:
            for task in (transcribing, switched_off):
                if not task.done():
                    task.cancel()


async def _wait_for_turn_end(ui: "AnyUI") -> None:
    """Wait for a cancelled turn to unwind, so what the user said starts a
    new turn instead of steering into the one being cancelled."""
    deadline = asyncio.get_running_loop().time() + _TURN_END_TIMEOUT
    while ui.is_thinking and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(_TURN_END_POLL)


def _quote(text: str) -> str:
    """*text* on one line, cut to fit a status bar."""
    line = " ".join(text.split())
    if len(line) > _MAX_QUOTED_CHARS:
        line = line[: _MAX_QUOTED_CHARS - 1].rstrip() + "…"
    return f'"{line}"'


def _to_output(ui: "AnyUI") -> Callable[[str], None]:
    return lambda message: ui.append_to_output(stylize_muted(f"\n  🎤 {message}\n"))
