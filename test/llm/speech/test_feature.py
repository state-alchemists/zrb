import logging
import threading
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from zrb.config.config import CFG
from zrb.contextvars import current_chat_session_id
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.speech import SpeechConfig, enable_speech
from zrb.llm.speech.feature import SpeechSession, describe_tool_call, is_answered_since
from zrb.llm.util.feature_config import close_feature_sessions


class PersistentHookTask:
    """An `LLMTask`-shaped task: one hook manager for the life of the task,
    with `append_hook_factory` applied to it immediately (docs/llm/hooks.md)."""

    def __init__(self):
        self.hook_manager = HookManager()
        self.prompt_manager = PromptManager(include_sections=[])
        self.hook_factories: list = []
        self.custom_commands: list = []
        self.stream_observers: list = []

    def append_hook_factory(self, factory):
        self.hook_factories.append(factory)
        factory(self.hook_manager)

    def remove_hook_factory(self, factory):
        self.hook_factories.remove(factory)

    def append_custom_command(self, command):
        self.custom_commands.append(command)

    def remove_custom_command(self, command):
        self.custom_commands.remove(command)

    def append_stream_observer(self, observer):
        self.stream_observers.append(observer)

    def remove_stream_observer(self, observer):
        self.stream_observers.remove(observer)


def _hook_count(manager: HookManager) -> int:
    registry = manager.registry
    return len(registry.get_global_hooks()) + sum(
        len(registry.get_hooks(event)) for event in HookEvent
    )


@contextmanager
def _as_session(name: str):
    """Run the block as chat session *name*, the way the web runner does."""
    token = current_chat_session_id.set(name)
    try:
        yield
    finally:
        current_chat_session_id.reset(token)


class FakeSpeaker:
    def __init__(self):
        self.said: list[str] = []
        self.cleared = 0
        self.closed = 0
        self.is_enabled = True

    def say(self, text, is_stale=None):
        self.said.append(text)

    def say_later(self, produce):
        """Run *produce* off the test's event loop, as the speaker's thread
        does."""
        produced = []
        worker = threading.Thread(target=lambda: produced.append(produce()))
        worker.start()
        worker.join()
        self.said.extend(produced)

    def clear(self):
        self.cleared += 1

    def close(self):
        self.closed += 1


def _session(**config) -> SpeechSession:
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
    session = _session()

    await session.handle_stop(_stop("**Done.** Tests pass: `pytest`."))

    assert session.speaker.said == ["Done. Tests pass: pytest."]


@pytest.mark.asyncio
async def test_a_sub_agent_reply_is_not_spoken():
    session = _session()

    await session.handle_stop(_stop("inner work", nested=True))

    assert session.speaker.said == []


@pytest.mark.asyncio
async def test_a_long_reply_is_read_whole():
    """Nothing caps what one turn says, so nothing is left unsaid and there is
    no note about what was."""
    session = _session()
    reply = "First part here. Second part is long. " * 3

    await session.handle_stop(_stop(reply))

    assert session.speaker.said == [reply.strip()]


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


def test_a_progress_only_session_gets_the_stop_hook_that_drops_its_lines():
    """`handle_stop` is where a turn's queued progress lines are invalidated, so
    a session that narrates without speaking the reply needs it too (review on
    #579)."""
    manager = MagicMock()

    _session(events=["progress"]).register_hooks(manager)

    (call,) = manager.add_hook.call_args_list
    assert call.kwargs["events"] == [HookEvent.STOP]


@pytest.mark.asyncio
async def test_a_progress_only_session_does_not_speak_the_reply():
    """The stop hook a `progress`-only session now gets must not make it start
    speaking replies (review on #579)."""
    session = _session(events=["progress"])

    await session.handle_stop(_stop("the reply"))

    assert session.speaker.said == []


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
    events = {call.kwargs["events"][0] for call in manager.add_hook.call_args_list}
    assert events == {
        HookEvent.STOP,
        HookEvent.PERMISSION_REQUEST,
        HookEvent.NOTIFICATION,
    }
    assert command.command == "/talk"
    assert command.handle({}, None) == f"🔊 Speech {'off' if enabled else 'on'}"


def test_enable_speech_on_a_task_without_commands_adds_only_hooks():
    """`LLMTask` takes no custom commands: speech adds its hooks, stream
    observer and live context, and no command."""

    class NoCommands:
        def __init__(self):
            self.factories = []
            self.stream_observers = []
            self.prompt_manager = PromptManager(include_sections=[])

        def append_hook_factory(self, factory):
            self.factories.append(factory)

        def append_stream_observer(self, observer):
            self.stream_observers.append(observer)

    task = NoCommands()

    enable_speech(task)

    assert len(task.factories) == 1
    assert len(task.stream_observers) == 1


def test_two_sessions_get_a_speaker_each():
    """One task serves every web chat connection, so a session that switched
    its speech off must not silence the next one."""
    chat = MagicMock()
    enable_speech(chat, SpeechConfig(enabled=True, commands=["/speech"]))
    (create_commands,) = chat.append_custom_command.call_args.args

    with _as_session("first"):
        (first,) = create_commands()
    with _as_session("second"):
        (second,) = create_commands()

    # Interleaved, so a shared speaker shows up: each session's own first press
    # reads its own state, still enabled, and switches off.
    assert first.handle({}, None) == "🔊 Speech off"
    assert second.handle({}, None) == "🔊 Speech off"
    assert first.handle({}, None) == "🔊 Speech on"


def test_enabling_speech_again_replaces_the_hooks_already_registered():
    task = PersistentHookTask()

    enable_speech(task, SpeechConfig(voice="alloy"))
    assert _hook_count(task.hook_manager) == 3

    enable_speech(task, SpeechConfig(voice="echo"))
    assert _hook_count(task.hook_manager) == 3


def test_enabling_speech_again_uses_the_new_config():
    """`llm_chat` enables speech at import, so a `zrb_init.py` that calls
    `enable_speech` with its own backend replaces that call. Keeping the first
    call's factory would build every later session from the config being
    replaced, and the documented replacement would do nothing."""
    task = MagicMock()

    enable_speech(task, SpeechConfig(commands=["/first"]))
    (first_commands,) = task.append_custom_command.call_args.args
    assert [c.command for c in first_commands()] == ["/first"]

    enable_speech(task, SpeechConfig(commands=["/second"]))
    (second_commands,) = task.append_custom_command.call_args.args
    assert [c.command for c in second_commands()] == ["/second"]


def test_a_task_reusing_one_manager_never_gains_a_second_set_of_hooks():
    """`execution.py` re-applies every factory on each run, so a task holding
    one manager used to speak each reply once more per run."""
    chat = MagicMock()
    enable_speech(chat)
    (register_hooks,) = chat.append_hook_factory.call_args.args
    manager = HookManager()

    for _ in range(4):
        register_hooks(manager)

    assert _hook_count(manager) == 3


def test_a_closed_session_is_dropped_so_the_next_one_starts_fresh():
    """Otherwise the registry keeps every session this process ever served,
    and the next session's `/speech` would toggle a dead one."""
    chat = MagicMock()
    enable_speech(chat, SpeechConfig(commands=["/speech"]))
    (create_commands,) = chat.append_custom_command.call_args.args

    with _as_session("first"):
        (before,) = create_commands()
        close_feature_sessions("first")
        (after,) = create_commands()

    assert before is not after


def test_closing_a_session_takes_its_hooks_back_out_and_stops_the_speaker():
    session = _session()
    manager = HookManager()

    session.register_hooks(manager)
    assert _hook_count(manager) == 3

    session.close()

    assert _hook_count(manager) == 0
    assert session.speaker.closed == 1


def test_speech_says_so_when_the_hook_allowlist_leaves_it_out(caplog, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_HOOKS", ["handle_stop", "my_hook"])

    with caplog.at_level(logging.WARNING, logger="zrb.llm.speech.feature"):
        _session()

    assert "handle_notification, handle_permission_request" in caplog.text
    assert "handle_stop" not in caplog.text


def test_speech_with_no_hook_allowlist_warns_of_nothing(caplog, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_HOOKS", [])

    with caplog.at_level(logging.WARNING, logger="zrb.llm.speech.feature"):
        _session()

    assert "allowlist" not in caplog.text


def test_speech_says_so_when_the_hook_subsystem_is_off(caplog, monkeypatch):
    monkeypatch.setattr(CFG, "HOOKS_ENABLED", False)

    with caplog.at_level(logging.WARNING, logger="zrb.llm.speech.feature"):
        enable_speech(PersistentHookTask())

    assert "ZRB_HOOKS_ENABLED" in caplog.text


@pytest.mark.asyncio
async def test_a_session_ignores_another_sessions_events_on_a_shared_manager():
    with _as_session("first"):
        first = _session()
    with _as_session("second"):
        second = _session()

        await first.handle_stop(_stop("for the second session"))
        await first.handle_permission_request(
            HookContext(
                event=HookEvent.PERMISSION_REQUEST, event_data={}, tool_name="Shell"
            )
        )
        await second.handle_stop(_stop("for the second session"))

    assert first.speaker.said == []
    assert second.speaker.said == ["for the second session"]


@pytest.mark.asyncio
async def test_a_question_is_spoken_clean_and_whole():
    session = _session()

    await session.handle_notification(
        HookContext(
            event=HookEvent.NOTIFICATION,
            event_data={},
            notification_type="elicitation_dialog",
            message="Pick `one`. " + "Very long detail. " * 10,
        )
    )

    assert session.speaker.said == [("Pick one. " + "Very long detail. " * 10).strip()]
