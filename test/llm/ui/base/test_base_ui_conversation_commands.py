"""Conversation slash-commands (`/save`, `/load`, `/rewind`, `/redirect`,
`/copy`) of `BaseUI`, driven through their public `handle_*_command` entry
points. The part under test composes its own `BaseUI` owner for state and
method calls, so each test drives `handle_*_command` and asserts on the
recorded output lines and the owner's observable state.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.snapshot import RestoreOutcome
from zrb.llm.snapshot.manager import Snapshot
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.ui_config import UIConfig

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


def _snapshot(sha: str, message_count: int = 0) -> Snapshot:
    return Snapshot(
        sha=sha,
        timestamp="2026-01-01 00:00:00",
        label="label",
        message_count=message_count,
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


@pytest.fixture
def rewind_ui(tmp_path, monkeypatch):
    # BaseUI snapshots its working directory: a small one of the test's own,
    # not the checkout the tests run from, whose size and platform decide how
    # long hashing it takes.
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "f.txt").write_text("content")
    monkeypatch.chdir(workdir)
    ui = _ConversationUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
        ui_config=UIConfig(**_COMMANDS),
        enable_rewind=True,
        snapshot_dir=str(tmp_path / "snapshots"),
    )
    ui.outputs = []
    return ui


async def _wait_output(ui, fragment: str) -> None:
    for _ in range(40):
        if any(fragment in line for line in ui.outputs):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"expected output {fragment!r} not recorded")


def test_save_command_saves_and_switches_session(conv_ui):
    conv_ui.history_manager.load.return_value = ["hist"]
    assert conv_ui.handle_save_command("save myconvo") is True
    conv_ui.history_manager.update.assert_called_once()
    conv_ui.history_manager.save.assert_called_once_with("myconvo")
    assert conv_ui.conversation_session_name == "myconvo"
    assert any("saved" in line for line in conv_ui.outputs)


def test_save_command_reports_history_failure(conv_ui):
    conv_ui.history_manager.load.side_effect = RuntimeError("boom")
    assert conv_ui.handle_save_command("save myconvo") is True
    assert conv_ui.conversation_session_name == "session-one"
    assert any("Failed to save" in line for line in conv_ui.outputs)


def test_save_command_bare_or_blank_argument(conv_ui):
    assert conv_ui.handle_save_command("save") is True  # warning, consumed
    assert any("name required" in line for line in conv_ui.outputs)
    assert conv_ui.handle_save_command("save   ") is True  # warning, consumed
    assert conv_ui.handle_save_command("unrelated") is False


def test_load_command_switches_session_and_resets_usage(conv_ui):
    conv_ui.history_manager.load.return_value = []
    assert conv_ui.handle_load_command("load second") is True
    assert conv_ui.conversation_session_name == "second"
    assert any("switched to" in line for line in conv_ui.outputs)
    assert conv_ui.usage.session_token_usage == (0, 0)


def test_load_command_rolls_back_on_failure(conv_ui):
    conv_ui.history_manager.load.side_effect = RuntimeError("boom")
    assert conv_ui.handle_load_command("load second") is True
    assert conv_ui.conversation_session_name == "session-one"
    assert any("Failed to load" in line for line in conv_ui.outputs)


def test_load_command_blank_argument_passes_through(conv_ui):
    assert conv_ui.handle_load_command("load   ") is True  # bare-warning consumed
    assert conv_ui.handle_load_command("stray text") is False


@pytest.mark.asyncio
async def test_save_command_carries_the_rewind_history_to_the_new_name(rewind_ui):
    """`/save` hands the saved conversation's rewind history to its new name,
    the way it hands it the chat history — the copy runs off the UI thread."""
    manager = rewind_ui.snapshot_manager
    await manager.take_init_snapshot()

    assert rewind_ui.handle_save_command("save myconvo") is True
    await asyncio.gather(*list(rewind_ui.background_tasks))

    assert rewind_ui.conversation_session_name == "myconvo"
    assert [s.label for s in manager.list_snapshots()] == ["init"]


def test_rewind_unavailable_when_disabled(conv_ui, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_ENABLE_REWIND", False)
    assert conv_ui.handle_rewind_command("rewind") is True
    assert any("not enabled" in line for line in conv_ui.outputs)


def test_rewind_unavailable_after_enabling_without_snapshot_scope(conv_ui, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_ENABLE_REWIND", True)
    assert conv_ui.handle_rewind_command("rewind") is True
    assert any("unavailable in this session" in line for line in conv_ui.outputs)


@pytest.mark.asyncio
async def test_rewind_lists_snapshots_when_bare(rewind_ui):
    rewind_ui.snapshot_manager.list_snapshots = lambda: [_snapshot("a" * 40, 3)]
    assert rewind_ui.handle_rewind_command("rewind") is True
    await _wait_output(rewind_ui, "Snapshots (newest first)")
    assert any("rewind <number>" in line.lower() for line in rewind_ui.outputs)


@pytest.mark.asyncio
async def test_rewind_shows_empty_state(rewind_ui):
    rewind_ui.snapshot_manager.list_snapshots = lambda: []
    assert rewind_ui.handle_rewind_command("rewind") is True
    await _wait_output(rewind_ui, "No snapshots yet")


@pytest.mark.asyncio
async def test_rewind_restores_by_index_and_trims_history(rewind_ui):
    rewind_ui.snapshot_manager.list_snapshots = lambda: [
        _snapshot("f" * 40, message_count=1)
    ]
    rewind_ui.history_manager.load.return_value = ["m1", "m2"]
    rewind_ui.snapshot_manager.restore_snapshot = AsyncMock(
        return_value=RestoreOutcome(restored=True)
    )
    assert rewind_ui.handle_rewind_command("rewind 1") is True
    await _wait_output(rewind_ui, "restored")
    rewind_ui.snapshot_manager.restore_snapshot.assert_awaited_once_with("f" * 40)
    rewind_ui.history_manager.update.assert_called_once()
    rewind_ui.history_manager.save.assert_called()
    assert rewind_ui.is_thinking is False


@pytest.mark.asyncio
async def test_rewind_reports_out_of_range_index(rewind_ui):
    rewind_ui.snapshot_manager.list_snapshots = lambda: [_snapshot("f" * 40)]
    assert rewind_ui.handle_rewind_command("rewind 42") is True
    await _wait_output(rewind_ui, "No snapshot at index")


@pytest.mark.asyncio
async def test_rewind_restores_by_sha_prefix(rewind_ui):
    rewind_ui.snapshot_manager.list_snapshots = lambda: [_snapshot("face" + "0" * 36)]
    rewind_ui.snapshot_manager.restore_snapshot = AsyncMock(
        return_value=RestoreOutcome(restored=True)
    )
    assert rewind_ui.handle_rewind_command("rewind face") is True
    await _wait_output(rewind_ui, "restored")
    rewind_ui.snapshot_manager.restore_snapshot.assert_awaited_once_with(
        "face" + "0" * 36
    )


@pytest.mark.asyncio
async def test_a_partial_restore_rewinds_the_chat_and_names_what_is_left(
    rewind_ui,
):
    rewind_ui.snapshot_manager.list_snapshots = lambda: [
        _snapshot("f" * 40, message_count=1)
    ]
    rewind_ui.history_manager.load.return_value = ["m1", "m2"]
    rewind_ui.snapshot_manager.restore_snapshot = AsyncMock(
        return_value=RestoreOutcome(restored=True, left_behind=("locked/f.txt",))
    )

    assert rewind_ui.handle_rewind_command("rewind 1") is True
    await _wait_output(rewind_ui, "except these files")

    output = "".join(rewind_ui.outputs)
    assert "- locked/f.txt" in output and "run the same /rewind again" in output
    rewind_ui.history_manager.update.assert_called_once()  # the chat rewound too


@pytest.mark.asyncio
async def test_rewind_reports_failed_restore(rewind_ui):
    rewind_ui.snapshot_manager.list_snapshots = lambda: [_snapshot("f" * 40)]
    rewind_ui.snapshot_manager.restore_snapshot = AsyncMock(
        return_value=RestoreOutcome(restored=False)
    )
    assert rewind_ui.handle_rewind_command("rewind 1") is True
    await _wait_output(rewind_ui, "Failed to restore snapshot")


def test_last_ai_response_falls_back_to_history(conv_ui):
    conv_ui.last_result_data = "live answer"
    assert conv_ui.last_ai_response() == "live answer"
    conv_ui.last_result_data = None
    conv_ui.history_manager.load.return_value = ["m1"]
    with patch(
        "zrb.llm.util.history_formatter.extract_last_response_text",
        return_value="from history",
    ):
        assert conv_ui.last_ai_response() == "from history"


def test_last_ai_response_empty_when_history_load_fails(conv_ui):
    conv_ui.last_result_data = None
    conv_ui.history_manager.load.side_effect = RuntimeError("boom")
    assert conv_ui.last_ai_response() == ""


def test_write_text_to_file_creates_parents(tmp_path):
    ui = _ConversationUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
        ui_config=UIConfig(**_COMMANDS),
    )
    target = tmp_path / "nested" / "out.txt"
    ui.write_text_to_file(str(target), "content")
    assert target.read_text() == "content"


def test_copy_to_clipboard_success_and_failure(conv_ui):
    with patch("zrb.llm.util.clipboard.copy_text", return_value=True):
        conv_ui.copy_to_clipboard_and_report("x", "copied!")
        assert any("copied!" in line for line in conv_ui.outputs)
    with patch("zrb.llm.util.clipboard.copy_text", return_value=False):
        conv_ui.copy_to_clipboard_and_report("x", "copied!")
        assert any("Failed to copy" in line for line in conv_ui.outputs)


def test_redirect_command_copies_last_ai_response(conv_ui):
    conv_ui.last_result_data = "some answer"
    with patch("zrb.llm.util.clipboard.copy_text", return_value=True):
        assert conv_ui.handle_redirect_command("redirect") is True
    assert any("copied" in line for line in conv_ui.outputs)


def test_redirect_command_with_nothing_to_copy(conv_ui):
    conv_ui.last_result_data = None
    conv_ui.history_manager.load.return_value = []
    assert conv_ui.handle_redirect_command("redirect") is True
    assert any("No AI response" in line for line in conv_ui.outputs)


def test_redirect_command_writes_to_file(conv_ui, tmp_path):
    conv_ui.last_result_data = "some answer"
    target = tmp_path / "out.txt"
    assert conv_ui.handle_redirect_command(f"redirect {target}") is True
    assert target.read_text() == "some answer"
    assert any("redirected" in line for line in conv_ui.outputs)


def test_redirect_command_reports_write_failure(conv_ui, tmp_path):
    conv_ui.last_result_data = "some answer"
    os_err_path = tmp_path  # a directory: open() must fail
    assert conv_ui.handle_redirect_command(f"redirect {os_err_path}") is True
    assert any("Failed to redirect" in line for line in conv_ui.outputs)


def test_redirect_command_blank_argument_passes_through(conv_ui):
    assert conv_ui.handle_redirect_command("redirect   ") is True


def test_copy_command_without_history(conv_ui):
    conv_ui.history_manager.load.return_value = []
    assert conv_ui.handle_copy_command("copy") is True
    assert any("No conversation history to copy" in line for line in conv_ui.outputs)


def test_copy_command_copies_full_transcript(conv_ui):
    conv_ui.history_manager.load.return_value = ["m1"]
    with (
        patch(
            "zrb.llm.util.history_formatter.format_history_as_text", return_value="text"
        ),
        patch("zrb.llm.util.clipboard.copy_text", return_value=True),
    ):
        assert conv_ui.handle_copy_command("copy") is True
    assert any("copied to clipboard" in line for line in conv_ui.outputs)


def test_copy_command_reports_format_error(conv_ui):
    conv_ui.history_manager.load.return_value = ["m1"]
    with patch(
        "zrb.llm.util.history_formatter.format_history_as_text",
        side_effect=RuntimeError("boom"),
    ):
        assert conv_ui.handle_copy_command("copy") is True
    assert any("Failed to copy transcript" in line for line in conv_ui.outputs)


def test_copy_command_writes_transcript_to_file(conv_ui, tmp_path):
    conv_ui.history_manager.load.return_value = ["m1"]
    target = tmp_path / "transcript.txt"
    with patch(
        "zrb.llm.util.history_formatter.format_history_as_text", return_value="text"
    ):
        assert conv_ui.handle_copy_command(f"copy {target}") is True
    assert target.read_text() == "text"
    assert any("saved to" in line for line in conv_ui.outputs)


def test_copy_command_to_file_without_history(conv_ui, tmp_path):
    conv_ui.history_manager.load.return_value = []
    assert conv_ui.handle_copy_command(f"copy {tmp_path / 'x.txt'}") is True
    assert any("No conversation history to save" in line for line in conv_ui.outputs)


def test_copy_command_blank_argument_passes_through(conv_ui):
    assert conv_ui.handle_copy_command("copy   ") is True


def test_rewind_follows_the_conversation_the_ui_switches_to(rewind_ui):
    rewind_ui.conversation_session_name = "loaded-conversation"

    assert rewind_ui.snapshot_manager.session_name == "loaded-conversation"


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
