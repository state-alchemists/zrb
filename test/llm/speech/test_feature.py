import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.types import HookEvent
from zrb.llm.speech import SpeechConfig, enable_speech
from zrb.llm.speech.feature import SpeechSession, describe_tool_call

NOTE = "Rest on screen."


class FakeSpeaker:
    def __init__(self):
        self.said: list[str] = []
        self.cleared = 0
        self.is_enabled = True

    def say(self, text):
        self.said.append(text)

    def clear(self):
        self.cleared += 1


def _session(**config) -> SpeechSession:
    config.setdefault("on_screen_note", NOTE)
    config.setdefault("enabled", True)
    session = SpeechSession(SpeechConfig(**config).resolve())
    session.speaker = FakeSpeaker()
    return session


def _stop(message: str, nested: bool = False) -> HookContext:
    return HookContext(
        event=HookEvent.STOP,
        event_data={"nested_run": nested},
        last_assistant_message=message,
    )


@pytest.mark.asyncio
async def test_a_short_reply_is_spoken_clean_and_whole():
    session = _session(max_chars=400)

    await session.handle_stop(_stop("**Done.** Tests pass: `pytest`."))

    assert session.speaker.said == ["Done. Tests pass: pytest."]


@pytest.mark.asyncio
async def test_a_sub_agent_reply_is_not_spoken():
    session = _session()

    await session.handle_stop(_stop("inner work", nested=True))

    assert session.speaker.said == []


@pytest.mark.asyncio
async def test_a_long_reply_is_cut_and_says_the_rest_is_on_screen():
    session = _session(max_chars=30, summarize=False)

    await session.handle_stop(_stop("First part here. Second part is long. " * 3))

    assert session.speaker.said == [f"First part here. {NOTE}"]


def _fake_summarizer(monkeypatch, output=None, error=None):
    prompts = []

    class Agent:
        async def run(self, text):
            prompts.append(text)
            if error:
                raise error
            return SimpleNamespace(output=output)

    def create(model=None, system_prompt=None):
        prompts.append(("model", model))
        return Agent()

    monkeypatch.setattr(
        "zrb.llm.agent.summarizer.create_summarizer_agent", create
    )
    return prompts


async def _settle(session):
    await asyncio.sleep(0)
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_a_long_reply_is_summarized_when_configured(monkeypatch):
    prompts = _fake_summarizer(monkeypatch, output="All tests pass.")
    session = _session(max_chars=30, summarize=True, summary_model="small")
    reply = "The long reply. " * 10

    session.say_reply(reply)
    await _settle(session)

    assert session.speaker.said == [f"All tests pass. {NOTE}"]
    assert prompts == [("model", "small"), reply]


@pytest.mark.asyncio
async def test_a_long_summary_is_cut_with_one_note(monkeypatch):
    _fake_summarizer(monkeypatch, output="Summary sentence one. " * 5)
    session = _session(max_chars=30, summarize=True)

    session.say_reply("The long reply. " * 10)
    await _settle(session)

    (said,) = session.speaker.said
    assert said.count(NOTE) == 1


@pytest.mark.asyncio
async def test_a_failed_summary_speaks_the_opening(monkeypatch):
    _fake_summarizer(monkeypatch, error=RuntimeError("rate limited"))
    session = _session(max_chars=30, summarize=True)

    session.say_reply("First part here. Second part is long. " * 3)
    await _settle(session)

    assert session.speaker.said == [f"First part here. {NOTE}"]


@pytest.mark.asyncio
async def test_approvals_and_questions_are_spoken():
    session = _session()

    await session.handle_permission_request(
        HookContext(
            event=HookEvent.PERMISSION_REQUEST,
            event_data={},
            tool_name="Write",
            tool_input={"path": "/tmp/a.py"},
        )
    )
    await session.handle_notification(
        HookContext(
            event=HookEvent.NOTIFICATION,
            event_data={},
            notification_type="elicitation_dialog",
            message="Which color?",
        )
    )
    await session.handle_notification(
        HookContext(
            event=HookEvent.NOTIFICATION,
            event_data={},
            notification_type="idle_prompt",
            message="Still there?",
        )
    )

    assert session.speaker.said == [
        "I need to write a file /tmp/a.py. I need your approval.",
        "Which color?",
    ]


@pytest.mark.parametrize(
    "tool, args, spoken",
    [
        ("Bash", {"command": "ls"}, "I need to run a shell command ls."),
        ("Grep", {}, "I need to use the Grep tool."),
        (None, None, "I need to run a tool."),
    ],
)
def test_describe_tool_call(tool, args, spoken):
    assert describe_tool_call(tool, args) == f"{spoken} I need your approval."


def test_only_the_configured_events_get_hooks():
    manager = MagicMock()

    _session(events=["reply"]).register_hooks(manager)

    (call,) = manager.add_hook.call_args_list
    assert call.kwargs["events"] == [HookEvent.STOP]


def test_the_speech_command_switches_speech_and_drops_the_queue():
    session = _session(commands=["/speech"])
    (command,) = session.create_commands()

    assert command.handle({}, None) == "🔊 Speech off"
    assert session.speaker.cleared == 1
    assert command.handle({}, None) == "🔊 Speech on"
    assert command.can_run_while_thinking


@pytest.mark.parametrize("enabled", [True, False])
def test_enable_speech_reads_cfg_when_a_session_starts(monkeypatch, enabled):
    chat = MagicMock()
    enable_speech(chat)
    (register_hooks,) = chat.append_hook_factory.call_args.args
    (create_commands,) = chat.append_custom_command.call_args.args
    manager = MagicMock()

    monkeypatch.setattr(CFG, "LLM_SPEECH_ENABLED", enabled)
    monkeypatch.setattr(CFG, "LLM_SPEECH_COMMANDS", ["/talk"])
    register_hooks(manager)
    (command,) = create_commands()

    # Offered either way, so speech that starts off can be switched on.
    assert manager.add_hook.call_count == 3
    assert command.command == "/talk"
    assert command.handle({}, None) == f"🔊 Speech {'off' if enabled else 'on'}"


def test_enable_speech_on_a_task_without_commands_adds_only_hooks():
    class HooksOnly:
        def __init__(self):
            self.factories = []

        def append_hook_factory(self, factory):
            self.factories.append(factory)

    task = HooksOnly()

    enable_speech(task)

    assert len(task.factories) == 1
