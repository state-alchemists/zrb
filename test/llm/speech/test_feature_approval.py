"""A spoken approval request is dropped once its prompt is answered."""

import time

import pytest

from zrb.config.config import CFG
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.speech import SpeechConfig
from zrb.llm.speech.feature import SpeechSession, describe_tool_call, is_answered_since
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


class TextSpeaker:
    def __init__(self):
        self.said: list[str] = []

    def say(self, text, is_stale=None):
        self.said.append(text)

    def close(self):
        pass


def _text_session(**config) -> tuple[SpeechSession, TextSpeaker]:
    session = SpeechSession(SpeechConfig(enabled=True, **config).resolve())
    speaker = TextSpeaker()
    session.speaker = speaker  # type: ignore[assignment]
    return session, speaker


@pytest.mark.asyncio
async def test_the_approval_request_follows_the_configured_template():
    session, speaker = _text_session(
        approval_message="Boleh saya {action}{target}?",
        approval_target_keys=["url"],
        approval_target_max_chars=5,
    )
    await session.handle_permission_request(
        HookContext(
            event=HookEvent.PERMISSION_REQUEST,
            event_data={},
            tool_name="WebFetch",
            tool_input={"path": "/tmp/a.py", "url": "https://x.io"},
        )
    )
    assert speaker.said == ["Boleh saya use the WebFetch tool https?"]


def test_a_zero_target_length_leaves_the_target_out():
    spoken = describe_tool_call(
        "Bash", {"command": "ls"}, message="{action}{target}.", target_max_chars=0
    )
    assert spoken == "run a shell command."


def test_the_approval_template_is_read_from_cfg_when_left_unset(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_SPEECH_APPROVAL_MESSAGE", "OK to {action}?")
    assert describe_tool_call("Bash", {}) == "OK to run a shell command?"


@pytest.mark.asyncio
async def test_a_question_with_no_text_says_the_configured_message():
    session, speaker = _text_session(question_message="Ada pertanyaan.")
    await session.handle_notification(
        HookContext(
            event=HookEvent.NOTIFICATION,
            event_data={},
            notification_type="elicitation_dialog",
            message="",
        )
    )
    assert speaker.said == ["Ada pertanyaan."]


def test_the_approval_action_comes_from_the_configured_patterns():
    actions = {"Write": "menulis berkas", "Mcp*": "memakai {tool}"}
    message = "{action}"
    assert describe_tool_call("Write", {}, message, actions=actions) == "menulis berkas"
    assert (
        describe_tool_call("McpGit", {}, message, actions=actions) == "memakai McpGit"
    )
    # No pattern matches: the tool's own name.
    assert describe_tool_call("Grep", {}, message, actions=actions) == "Grep"


def test_the_approval_actions_are_read_from_cfg_when_left_unset(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_SPEECH_APPROVAL_ACTIONS", '{"*": "memakai {tool}"}')
    assert describe_tool_call("Bash", {}, "{action}") == "memakai Bash"
