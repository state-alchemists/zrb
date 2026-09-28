"""A spoken approval request is dropped once its prompt is answered."""

import time

import pytest

from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.speech import SpeechConfig
from zrb.llm.speech.feature import SpeechSession, is_answered_since
from zrb.llm.util.feature_config import reset_session_ui, set_session_ui


class StaleCheckSpeaker:
    def __init__(self):
        self.stale_checks: list = []

    def say(self, text, is_stale=None):
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


def _assert_goes_stale_once_answered(ui, is_stale) -> None:
    assert not is_stale()
    prompt = ui.ask()
    assert not is_stale()
    prompt[1] = True
    assert is_stale()


@pytest.mark.asyncio
async def test_a_spoken_approval_goes_stale_once_its_prompt_is_answered(session_ui):
    session, speaker = _session()

    await session.handle_permission_request(
        HookContext(
            event=HookEvent.PERMISSION_REQUEST, event_data={}, tool_name="Shell"
        )
    )

    (is_stale,) = speaker.stale_checks
    _assert_goes_stale_once_answered(session_ui, is_stale)


@pytest.mark.asyncio
async def test_the_session_ui_reaches_a_hook_run_by_the_hook_manager(session_ui):
    """Hooks run on a pool thread with the ambient UI cleared, so the session's
    UI has to reach them another way."""
    session, speaker = _session()
    manager = HookManager(search_dirs=[])
    session.register_hooks(manager)

    await manager.execute_hooks(HookEvent.PERMISSION_REQUEST, {}, tool_name="Shell")

    (is_stale,) = speaker.stale_checks
    _assert_goes_stale_once_answered(session_ui, is_stale)


def test_an_older_prompt_answered_does_not_make_a_new_approval_stale():
    ui = PromptUI()
    older = ui.ask()
    is_answered = is_answered_since(ui, time.monotonic())

    older[1] = True
    assert not is_answered()
    ui.ask()[1] = True  # the prompt after the hook
    assert is_answered()


def test_a_ui_that_cannot_time_its_prompt_never_reads_as_answered():
    is_answered = is_answered_since(None, time.monotonic())

    assert not is_answered()
