"""A spoken question is dropped once its prompt is answered.

An approval request already says what makes it stale, so pressing `y` cuts it
off mid-sentence. The question zrb speaks before showing an `AskUserQuestion`
dialog said nothing of the kind, so answering with the arrow keys — or by
typing into the prompt — left the voice reading on.

Nothing here hooks the keyboard: the prompt's own future is the signal, which
is why one predicate covers both ways of answering.
"""

import time

import pytest

from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.speech import SpeechConfig
from zrb.llm.speech.feature import SpeechSession
from zrb.llm.util.feature_config import reset_session_ui, set_session_ui


class StaleCheckSpeaker:
    """Records the staleness check each utterance was given."""

    def __init__(self):
        self.stale_checks: list = []

    def say(self, text, is_stale=None, voice="", cut_when_stale=True):
        self.stale_checks.append(is_stale)

    def close(self):
        pass


class PromptUI:
    """Dates each prompt it asks, as a UI does."""

    def __init__(self):
        self.prompts: list[list] = []  # [asked at, is answered]

    def ask(self) -> list:
        prompt = [time.monotonic(), False]
        self.prompts.append(prompt)
        return prompt

    def is_prompt_answered_since(self, asked_at: float) -> bool:
        return next((p[1] for p in self.prompts if p[0] >= asked_at), False)


@pytest.fixture
def session_ui():
    """A UI bound to the session, reporting when its prompt appeared."""
    ui = PromptUI()
    set_session_ui(ui)  # type: ignore[arg-type]
    yield ui
    reset_session_ui()


def _session() -> tuple[SpeechSession, StaleCheckSpeaker]:
    session = SpeechSession(SpeechConfig(enabled=True).resolve())
    speaker = StaleCheckSpeaker()
    session.speaker = speaker  # type: ignore[assignment]
    return session, speaker


def _question(message: str = "Which color?") -> HookContext:
    return HookContext(
        event=HookEvent.NOTIFICATION,
        event_data={},
        notification_type="elicitation_dialog",
        message=message,
    )


def _assert_goes_stale_once_answered(ui, is_stale) -> None:
    assert not is_stale()
    prompt = ui.ask()
    assert not is_stale()
    prompt[1] = True
    assert is_stale()


@pytest.mark.asyncio
async def test_a_spoken_question_goes_stale_once_its_prompt_is_answered(session_ui):
    session, speaker = _session()

    await session.handle_notification(_question())

    (is_stale,) = speaker.stale_checks
    _assert_goes_stale_once_answered(session_ui, is_stale)


@pytest.mark.asyncio
async def test_a_question_with_no_text_still_watches_its_prompt(session_ui):
    """The configured fallback is the same utterance and must go stale too."""
    session, speaker = _session()

    await session.handle_notification(_question(""))

    (is_stale,) = speaker.stale_checks
    _assert_goes_stale_once_answered(session_ui, is_stale)


@pytest.mark.asyncio
async def test_the_session_ui_reaches_the_question_hook_through_the_manager(
    session_ui,
):
    """Hooks run on a pool thread with the ambient UI cleared, so the session's
    UI has to reach them another way."""
    session, speaker = _session()
    manager = HookManager(search_dirs=[])
    session.register_hooks(manager)

    await manager.execute_hooks(
        HookEvent.NOTIFICATION,
        {},
        message="Which color?",
        notification_type="elicitation_dialog",
    )

    (is_stale,) = speaker.stale_checks
    _assert_goes_stale_once_answered(session_ui, is_stale)
