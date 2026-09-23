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
def rewind_ui(tmp_path):
    ui = _ConversationUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
        ui_config=UIConfig(**_COMMANDS),
        enable_rewind=True,
        snapshot_dir=str(tmp_path),
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


def test_rewind_unavailable_when_disabled(conv_ui):
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
    rewind_ui.snapshot_manager.restore_snapshot = AsyncMock(return_value=True)
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
    rewind_ui.snapshot_manager.restore_snapshot = AsyncMock(return_value=True)
    assert rewind_ui.handle_rewind_command("rewind face") is True
    await _wait_output(rewind_ui, "restored")
    rewind_ui.snapshot_manager.restore_snapshot.assert_awaited_once_with(
        "face" + "0" * 36
    )


@pytest.mark.asyncio
async def test_rewind_reports_failed_restore(rewind_ui):
    rewind_ui.snapshot_manager.list_snapshots = lambda: [_snapshot("f" * 40)]
    rewind_ui.snapshot_manager.restore_snapshot = AsyncMock(return_value=False)
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
    with patch(
        "zrb.llm.util.history_formatter.format_history_as_text", return_value="text"
    ), patch("zrb.llm.util.clipboard.copy_text", return_value=True):
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