"""Auto-naming a conversation and restoring its sub-agent sessions on `/load`
(ADR-0109), driven through `stream_ai_response` and `handle_load_command`."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.ui_config import UIConfig


@pytest.fixture(autouse=True)
def _auto_naming_on(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_AUTO_NAME_ENABLED", "on")


_COMMANDS = dict(
    conversation_session_name="session-one",
    exit_commands=["exit"],
    info_commands=["info"],
    save_commands=["save"],
    load_commands=["load"],
    rewind_commands=["rewind"],
    redirect_output_commands=["redirect"],
    copy_commands=["copy"],
)


class _ConversationUI(BaseUI):
    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        self.outputs.append(kind + ":" + sep.join(str(v) for v in values))

    async def ask_user(self, prompt: str) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0

    async def run_async(self) -> str:
        return self.last_output


@pytest.fixture
def conv_ui():
    ui = _ConversationUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
        ui_config=UIConfig(**_COMMANDS),
    )
    ui.outputs = []
    return ui


async def _wait_output(ui, fragment: str) -> None:
    for _ in range(40):
        if any(fragment in line for line in ui.outputs):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"expected output {fragment!r} not recorded")


@pytest.mark.asyncio
async def test_a_generated_name_is_replaced_by_a_topic_name(conv_ui):
    conv_ui.conversation_session_name = "bold-arch-1234"
    conv_ui.llm_task.async_run = AsyncMock(return_value="hi!")
    with patch(
        "zrb.llm.ui.base.conversation_commands.suggest_slug",
        AsyncMock(return_value="greetings"),
    ):
        await conv_ui.stream_ai_response(conv_ui.llm_task, "hello")
        await _wait_output(conv_ui, "named")
    conv_ui.history_manager.rename.assert_called_once_with(
        "bold-arch-1234", "bold-arch-1234-greetings"
    )
    assert conv_ui.conversation_session_name == "bold-arch-1234-greetings"


@pytest.mark.asyncio
async def test_a_chosen_name_is_never_renamed(conv_ui):
    with patch(
        "zrb.llm.ui.base.conversation_commands.suggest_slug",
        AsyncMock(return_value="greetings"),
    ) as suggest:
        conv_ui.llm_task.async_run = AsyncMock(return_value="hi!")
        await conv_ui.stream_ai_response(conv_ui.llm_task, "hello")
        await asyncio.sleep(0.05)
    suggest.assert_not_called()
    assert conv_ui.conversation_session_name == "session-one"


def test_load_restores_the_conversations_sub_agent_sessions(conv_ui):
    # lazy: the registry pulls in pydantic_ai
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSessionRegistry

    registry = LiveSubAgentSessionRegistry()
    conv_ui.history_manager.search.return_value = [
        "second-sub-reviewer-abcd1234",
        "other-sub-reviewer-ffff0000",
        "second",
    ]
    conv_ui.history_manager.load.return_value = ["hist"]
    manager = MagicMock()
    with (
        patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            registry,
        ),
        patch("zrb.llm.agent.subagent.manager.sub_agent_manager", manager),
    ):
        conv_ui.handle_load_command("load second")

    [session] = registry.active("second")
    assert (session.agent_id, session.agent_name) == ("abcd1234", "reviewer")
    assert session.state == "idle" and session.authority is None
    assert session.history == ["hist"]


@pytest.mark.asyncio
async def test_a_failed_naming_keeps_the_generated_name(conv_ui):
    from zrb.llm.util.conversation_naming import ConversationNamingError

    conv_ui.conversation_session_name = "bold-arch-1234"
    conv_ui.llm_task.async_run = AsyncMock(return_value="hi!")
    with patch(
        "zrb.llm.ui.base.conversation_commands.suggest_slug",
        AsyncMock(side_effect=ConversationNamingError("down")),
    ):
        await conv_ui.stream_ai_response(conv_ui.llm_task, "hello")
        await asyncio.sleep(0.05)
    conv_ui.history_manager.rename.assert_not_called()
    assert conv_ui.conversation_session_name == "bold-arch-1234"


@pytest.mark.asyncio
async def test_a_rename_waits_for_the_running_turn_and_uses_the_first_message(conv_ui):
    conv_ui.conversation_session_name = "bold-arch-1234"
    conv_ui.llm_task.async_run = AsyncMock(return_value="hi!")
    release = asyncio.Event()

    async def slow_slug(message):
        await release.wait()
        return "first-topic"

    suggest = AsyncMock(side_effect=slow_slug)
    with patch("zrb.llm.ui.base.conversation_commands.suggest_slug", suggest):
        await conv_ui.stream_ai_response(conv_ui.llm_task, "first message")
        conv_ui.is_thinking = True  # a second turn starts while naming is pending
        release.set()
        await asyncio.sleep(0.05)
        conv_ui.history_manager.rename.assert_not_called()
        conv_ui.is_thinking = False  # that turn ends
        await _wait_output(conv_ui, "named")
    suggest.assert_called_once_with("first message")
    assert conv_ui.conversation_session_name == "bold-arch-1234-first-topic"


def test_load_restores_sub_agents_of_a_name_that_needed_sanitizing(conv_ui):
    # lazy: the registry pulls in pydantic_ai
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSessionRegistry

    registry = LiveSubAgentSessionRegistry()
    conv_ui.history_manager.search.return_value = ["customeracme-sub-reviewer-abcd1234"]
    conv_ui.history_manager.load.return_value = ["hist"]
    with (
        patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            registry,
        ),
        patch("zrb.llm.agent.subagent.manager.sub_agent_manager", MagicMock()),
    ):
        conv_ui.handle_load_command("load customer/acme")

    assert [s.agent_id for s in registry.active("customer/acme")] == ["abcd1234"]


def test_a_failed_load_leaves_no_half_restored_sub_agent_sessions(conv_ui):
    # lazy: the registry pulls in pydantic_ai
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSessionRegistry

    registry = LiveSubAgentSessionRegistry()
    conv_ui.history_manager.search.return_value = [
        "second-sub-reviewer-abcd1234",
        "second-sub-reviewer-ffff0000",
    ]
    conv_ui.history_manager.load.side_effect = [[], ["ok"], RuntimeError("corrupt")]
    with (
        patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            registry,
        ),
        patch("zrb.llm.agent.subagent.manager.sub_agent_manager", MagicMock()),
    ):
        conv_ui.handle_load_command("load second")

    assert registry.active("second") == []
    assert conv_ui.conversation_session_name == "session-one"


def test_a_transcript_found_twice_is_restored_once(conv_ui):
    # lazy: the registry pulls in pydantic_ai
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSessionRegistry

    registry = LiveSubAgentSessionRegistry()
    name = "second-sub-reviewer-abcd1234"
    conv_ui.history_manager.search.return_value = [name, name]
    conv_ui.history_manager.load.return_value = ["hist"]
    with (
        patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            registry,
        ),
        patch("zrb.llm.agent.subagent.manager.sub_agent_manager", MagicMock()),
    ):
        conv_ui.handle_load_command("load second")

    assert len(registry.active("second")) == 1


@pytest.mark.asyncio
async def test_switching_conversations_mid_naming_still_names_the_new_one(conv_ui):
    conv_ui.conversation_session_name = "bold-arch-1234"
    conv_ui.llm_task.async_run = AsyncMock(return_value="hi!")
    release = asyncio.Event()

    async def slow_slug(message):
        await release.wait()
        return message

    with patch(
        "zrb.llm.ui.base.conversation_commands.suggest_slug",
        AsyncMock(side_effect=slow_slug),
    ):
        await conv_ui.stream_ai_response(conv_ui.llm_task, "first")
        conv_ui.conversation_session_name = "calm-atom-5678"  # /load another one
        await conv_ui.stream_ai_response(conv_ui.llm_task, "second")
        release.set()
        await _wait_output(conv_ui, "calm-atom-5678-second")


def test_a_transcript_that_loads_empty_is_not_restored(conv_ui):
    # lazy: the registry pulls in pydantic_ai
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSessionRegistry

    registry = LiveSubAgentSessionRegistry()
    conv_ui.history_manager.search.return_value = ["second-sub-reviewer-abcd1234"]
    conv_ui.history_manager.load.return_value = []
    with (
        patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            registry,
        ),
        patch("zrb.llm.agent.subagent.manager.sub_agent_manager", MagicMock()),
    ):
        conv_ui.handle_load_command("load second")

    assert registry.active("second") == []


def test_load_by_the_topic_name_restores_the_sub_agents_of_its_key(conv_ui):
    # lazy: the registry pulls in pydantic_ai
    from zrb.llm.agent.subagent.live_session import LiveSubAgentSessionRegistry

    registry = LiveSubAgentSessionRegistry()
    conv_ui.history_manager.search.return_value = [
        "bold-arch-1234-sub-reviewer-abcd1234"
    ]
    conv_ui.history_manager.load.return_value = ["hist"]
    with (
        patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            registry,
        ),
        patch("zrb.llm.agent.subagent.manager.sub_agent_manager", MagicMock()),
    ):
        conv_ui.handle_load_command("load bold-arch-1234-greetings")

    [session] = registry.active("bold-arch-1234")
    assert session.agent_id == "abcd1234"
    assert session.persist_history is not None
