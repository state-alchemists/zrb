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
from zrb.llm.dictation.listen import import_audio, listen
from zrb.llm.dictation.words import split_phrases, strip_wake_word, to_answer
from zrb.llm.ui.trigger import TriggerReply
from zrb.llm.util.feature_config import replace_feature_sessions, replace_registration
from zrb.util.cli.style import stylize_muted

if TYPE_CHECKING:
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.ui.base.ui import BaseUI

logger = logging.getLogger(__name__)

HANDS_FREE = "hands_free"


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
        self._report: Callable[[str], None] = logger.warning
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
        self.is_hands_free = False
        self._hands_free_off.set()
        if self._stop_recording is not None:
            self._stop_recording.set()

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
                self._report = _to_output(ui)
        self.is_hands_free = not self.is_hands_free
        if self.is_hands_free:
            self._hands_free_off.clear()
        else:
            self._hands_free_off.set()
        if self._stop_recording is not None:
            self._stop_recording.set()
        return f"🎤 Hands-free {'on' if self.is_hands_free else 'off'}"

    async def _record_into(self, ui: "BaseUI", stop: asyncio.Event) -> str:
        await self.backend.prepare(_to_output(ui))
        commands = ", ".join(self._config.commands or [])
        ui.append_to_output(
            stylize_muted(f"\n  🎤 Listening... ({commands} or a pause to stop)\n")
        )
        audio = await self._record_one(stop)
        text = (await self.backend.transcribe(audio)).strip() if audio else ""
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
                async with aclosing(self._replies()) as replies:
                    async for reply in replies:
                        yield reply
            except Exception as exc:
                # Stop rather than retry a broken microphone forever.
                self._report(f"Hands-free dictation stopped: {exc}")
                self.is_hands_free = False

    async def _replies(self) -> AsyncGenerator[TriggerReply, None]:
        armed_until = 0.0
        # aclosing so switching hands-free off closes the microphone as soon as
        # the utterance in flight is dropped, not at finalization.
        async with aclosing(listen(self._config, lambda: self.is_hands_free)) as mic:
            async for utterance in mic:
                try:
                    text = await self._transcribe_or_drop(utterance.audio)
                except Exception as exc:
                    self._report(f"Hands-free transcription failed: {exc}")
                    continue
                if text is None:
                    return
                if not text:
                    continue
                command = strip_wake_word(text, self._wake_words)
                # Against when the utterance was spoken, not when transcription
                # finished: transcription alone can take seconds.
                if command is None and utterance.started_at < armed_until:
                    command = text
                if command is None:
                    continue
                if not command:
                    # The wake word alone: people pause after it.
                    armed_until = utterance.ended_at + (self._config.wake_window or 0)
                    continue
                armed_until = 0.0
                yield TriggerReply(
                    command,
                    approval=to_answer(command, self._approve_words, self._deny_words),
                    started_at=utterance.started_at,
                )

    async def _transcribe_or_drop(self, audio: bytes) -> str | None:
        """*audio*'s transcript, or ``None`` when hands-free was switched off
        while it was being transcribed — the user said stop, so that utterance
        is theirs, not the model's."""
        transcribing = asyncio.ensure_future(self.backend.transcribe(audio))
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


def _to_output(ui: "BaseUI") -> Callable[[str], None]:
    return lambda message: ui.append_to_output(stylize_muted(f"\n  🎤 {message}\n"))
