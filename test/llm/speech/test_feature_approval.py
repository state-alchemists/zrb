"""A spoken approval request is dropped once its prompt is answered."""

import time
from types import SimpleNamespace

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


@pytest.fixture
def session_ui():
    """A UI bound to the session, reporting when its prompt appeared."""
    ui = SimpleNamespace(pending_answer_since=None)
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
    ui.pending_answer_since = time.monotonic()
    assert not is_stale()
    ui.pending_answer_since = None
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
    ui = SimpleNamespace(pending_answer_since=time.monotonic() - 5)
    is_answered = is_answered_since(ui, time.monotonic())

    assert not is_answered()
    ui.pending_answer_since = None
    assert not is_answered()
    ui.pending_answer_since = time.monotonic()
    assert not is_answered()
    ui.pending_answer_since = time.monotonic() + 1  # the next prompt
    assert is_answered()


def test_a_ui_that_cannot_time_its_prompt_never_reads_as_answered():
    is_answered = is_answered_since(None, time.monotonic())

    assert not is_answered()


def test_a_prompt_answered_before_the_first_check_still_reads_as_answered():
    ui = SimpleNamespace(pending_answer_since=None)
    is_answered = is_answered_since(ui, time.monotonic())

    ui.pending_answer_since = time.monotonic()
    time.sleep(0.3)  # the prompt is up long enough to be seen
    ui.pending_answer_since = None

    assert is_answered()
