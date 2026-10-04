import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.ui.base.commands import BaseUICommands


def test_handle_exit_command(ui):
    assert ui.handle_exit_command("/exit") is True
    assert ui.exited is True
    assert ui.handle_exit_command("hello") is False


def test_handle_info_command(ui):
    assert ui.handle_info_command("/help") is True
    assert any("Available Commands" in o for o in ui.outputs)


@pytest.mark.asyncio
async def test_handle_save_command(ui):
    ui.history_manager.load.return_value = ["msg1"]
    ui.snapshot_manager.copy_history = AsyncMock()
    previous = ui.conversation_session_name

    assert ui.handle_save_command("/save my-session") is True
    await asyncio.gather(*ui.background_tasks)

    ui.history_manager.update.assert_called_with("my-session", ["msg1"])
    ui.history_manager.save.assert_called_with("my-session")
    # The saved copy keeps the conversation's rewind history.
    ui.snapshot_manager.copy_history.assert_awaited_once_with(previous, "my-session")
    assert "saved" in "".join(ui.outputs)


def test_save_without_a_running_loop_still_registers_the_copy(ui):
    """Registered on the call, so the next operation applies it even with no
    loop to run the rest on."""
    ui.history_manager.load.return_value = ["msg1"]
    ui.snapshot_manager.copy_history = AsyncMock()
    previous = ui.conversation_session_name

    assert ui.handle_save_command("/save my-session") is True

    ui.history_manager.save.assert_called_with("my-session")
    ui.snapshot_manager.copy_history.assert_called_once_with(previous, "my-session")


def test_handle_load_command(ui):
    ui.history_manager.load.return_value = []
    assert ui.handle_load_command("/load other-session") is True
    assert ui.conversation_session_name == "other-session"
    assert "switched" in "".join(ui.outputs)


def test_handle_redirect_command(ui, tmp_path):
    out_file = tmp_path / "output.txt"
    assert ui.handle_redirect_command(f"/redirect {out_file}") is True
    assert out_file.read_text() == "some ai output"
    assert "redirected" in "".join(ui.outputs)


def test_handle_redirect_command_bare(ui):
    """Bare /redirect copies last_output to clipboard."""
    ui.redirect_output_commands = ["/redirect"]
    ui.last_output = "clipboard content"
    with patch("zrb.llm.util.clipboard.copy_text", return_value=True) as mock_copy:
        result = ui.handle_redirect_command("/redirect")

    assert result is True
    mock_copy.assert_called_once_with("clipboard content")


def test_handle_redirect_command_bare_falls_back_to_history(ui):
    """Bare /redirect uses the last history response when no live output exists.

    Reproduces `chat --session <name>`: history is replayed but last_output
    is empty until a live turn runs.
    """
    ui.redirect_output_commands = ["/redirect"]
    ui.last_output = ""
    ui.history_manager.load.return_value = [{"role": "assistant", "content": "x"}]
    with patch("zrb.llm.util.clipboard.copy_text", return_value=True) as mock_copy:
        with patch(
            "zrb.llm.util.history_formatter.extract_last_response_text",
            return_value="from history",
        ):
            result = ui.handle_redirect_command("/redirect")

    assert result is True
    mock_copy.assert_called_once_with("from history")


def test_handle_redirect_command_bare_no_output_no_history(ui):
    """Bare /redirect errors when neither live output nor history text exists."""
    ui.redirect_output_commands = ["/redirect"]
    ui.last_output = ""
    ui.history_manager.load.return_value = []
    with patch("zrb.llm.util.clipboard.copy_text") as mock_copy:
        with patch(
            "zrb.llm.util.history_formatter.extract_last_response_text",
            return_value="",
        ):
            result = ui.handle_redirect_command("/redirect")

    assert result is True
    mock_copy.assert_not_called()
    assert any("no ai response" in o.lower() for o in ui.outputs)


def test_handle_copy_command(ui):
    """Bare /copy copies full transcript to clipboard."""
    ui.copy_commands = ["/copy"]
    ui.history_manager.load.return_value = [{"role": "user", "content": "hi"}]

    with patch("zrb.llm.util.clipboard.copy_text", return_value=True) as mock_copy:
        with patch(
            "zrb.llm.util.history_formatter.format_history_as_text",
            return_value="copy text",
        ):
            result = ui.handle_copy_command("/copy")

    assert result is True
    mock_copy.assert_called_once_with("copy text")


def test_handle_copy_command_to_file(ui, tmp_path):
    """Copy with path writes transcript to file."""
    ui.copy_commands = ["/copy"]
    ui.history_manager.load.return_value = [{"role": "assistant", "content": "msg"}]
    out_file = tmp_path / "transcript.txt"

    with patch(
        "zrb.llm.util.history_formatter.format_history_as_text",
        return_value="file content",
    ):
        result = ui.handle_copy_command(f"/copy {out_file}")

    assert result is True
    assert out_file.read_text() == "file content"
    assert any("saved" in o.lower() for o in ui.outputs)


def test_handle_copy_command_no_history(ui):
    """Copy shows error when no history."""
    ui.copy_commands = ["/copy"]
    ui.history_manager.load.return_value = []

    result = ui.handle_copy_command("/copy")

    assert result is True
    assert any("no conversation" in o.lower() for o in ui.outputs)


def test_handle_attach_command(ui, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    assert ui.handle_attach_command(f"/attach {f}") is True
    assert str(f) in ui.pending_attachments


def test_handle_attach_command_not_found(ui, tmp_path):
    missing = tmp_path / "missing.txt"
    assert ui.handle_attach_command(f"/attach {missing}") is True
    assert ui.pending_attachments == []
    assert any("not found" in o.lower() for o in ui.outputs)


def test_handle_attach_command_directory(ui, tmp_path):
    assert ui.handle_attach_command(f"/attach {tmp_path}") is True
    assert ui.pending_attachments == []
    assert any("not found" in o.lower() for o in ui.outputs)


def test_handle_attach_command_unsupported_type(ui, tmp_path):
    f = tmp_path / "test.xyz"
    f.write_text("data")
    assert ui.handle_attach_command(f"/attach {f}") is True
    assert ui.pending_attachments == []
    assert any("unsupported file type" in o.lower() for o in ui.outputs)


def test_handle_attach_command_oversized(ui, tmp_path, monkeypatch):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 1)
    assert ui.handle_attach_command(f"/attach {f}") is True
    assert ui.pending_attachments == []
    assert any("too large" in o.lower() for o in ui.outputs)


def test_handle_attach_command_already_attached(ui, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    ui.handle_attach_command(f"/attach {f}")
    ui.handle_attach_command(f"/attach {f}")
    assert ui.pending_attachments == [str(f)]
    assert any("already attached" in o.lower() for o in ui.outputs)


def test_toggle_yolo(ui):
    ui.toggle_yolo()
    assert ui.yolo is True
    ui.toggle_yolo()
    assert ui.yolo is False


def test_handle_toggle_yolo_selective(ui):
    assert ui.handle_toggle_yolo("/yolo Write,Edit") is True
    assert ui.yolo == frozenset(["Write", "Edit"])


def test_current_cycle_mode_reports_each_state(ui):
    assert ui.current_cycle_mode() == "normal"
    ui.yolo = frozenset(["Write", "Edit"])
    assert ui.current_cycle_mode() == "accept_edits"
    ui.yolo = frozenset(["Read", "Bash"])
    assert ui.current_cycle_mode() == "custom"
    ui.yolo = True
    assert ui.current_cycle_mode() == "yolo"
    ui.yolo = False
    ui.plan_mode_active = True
    # Plan takes precedence over any yolo value.
    ui.yolo = frozenset(["Write", "Edit"])
    assert ui.current_cycle_mode() == "plan"


def test_cycle_mode_advances_normal_to_edits_to_plan_to_normal(ui):
    ui.yolo = False
    ui.plan_mode_active = False
    assert ui.current_cycle_mode() == "normal"
    ui.cycle_mode()
    assert ui.current_cycle_mode() == "accept_edits"
    assert ui.yolo == frozenset(["Write", "Edit"])
    ui.cycle_mode()
    assert ui.current_cycle_mode() == "plan"
    assert ui.plan_mode_active is True
    assert ui.yolo is False  # plan and yolo never stack
    ui.cycle_mode()
    assert ui.current_cycle_mode() == "normal"
    assert ui.plan_mode_active is False
    assert ui.yolo is False


def test_cycle_mode_resets_off_cycle_yolo_into_cycle(ui):
    # Full yolo (set via Ctrl+Y / /yolo) is off-cycle; Shift+Tab resets to normal.
    ui.yolo = True
    ui.plan_mode_active = False
    ui.cycle_mode()
    assert ui.current_cycle_mode() == "normal"
    assert ui.yolo is False


def test_handle_set_model_command(ui):
    assert ui.handle_set_model_command("/model gpt-4") is True
    assert ui.model == "gpt-4"
    assert "switched" in "".join(ui.outputs)


def test_handle_set_model_command_small_variant(ui):
    assert ui.handle_set_model_command("/model small gpt-4o-mini") is True
    assert ui.small_model == "gpt-4o-mini"
    assert "Small model switched to: gpt-4o-mini" in "".join(ui.outputs)


def test_handle_set_model_command_multimodal_variant(ui):
    assert ui.handle_set_model_command("/model multimodal gemini-flash") is True
    assert ui.multimodal_model == "gemini-flash"
    assert "Multimodal model switched to: gemini-flash" in "".join(ui.outputs)


def test_handle_set_model_command_ignored_while_thinking(ui):
    ui.is_thinking = True
    assert ui.handle_set_model_command("/model gpt-5") is False
    assert ui.model == "test-model"


def test_handle_set_model_command_survives_prompt_manager_error(ui):
    """A prompt-manager failure is debug-logged; the switch itself still lands."""
    ui.llm_task = MagicMock()
    type(ui.llm_task).prompt_manager = PropertyMock(
        side_effect=RuntimeError("no manager")
    )
    assert ui.handle_set_model_command("/model gpt-4-turbo") is True
    assert ui.model == "gpt-4-turbo"


def test_handle_set_command_updates_cfg(ui, monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MODEL", raising=False)
    assert ui.handle_set_command("/set LLM_MODEL my-model") is True
    assert CFG.LLM_MODEL == "my-model"
    assert "LLM_MODEL" in "".join(ui.outputs)


def test_handle_set_command_cfg_name_is_case_insensitive(ui, monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MODEL", raising=False)
    assert ui.handle_set_command("/set llm_model my-model") is True
    assert CFG.LLM_MODEL == "my-model"


def test_handle_set_command_uppercase_alias_drives_setting(ui, monkeypatch):
    """`/SET` is classified as a command case-insensitively, so the handler
    must match the same alias instead of forwarding the input to the model."""
    ui.set_commands = ["/SET"]
    monkeypatch.delenv("ZRB_LLM_MODEL", raising=False)
    assert ui.handle_set_command("/SET LLM_MODEL my-model") is True
    assert CFG.LLM_MODEL == "my-model"


def test_handle_set_command_unknown_name(ui):
    assert ui.handle_set_command("/set LLM_MODELL x") is True
    joined = "".join(ui.outputs)
    assert "LLM_MODELL" in joined
    assert "LLM_MODEL" in joined  # the suggestion


def test_handle_set_command_uncastable_value(ui):
    assert ui.handle_set_command("/set LLM_MAX_REQUEST_PER_MINUTE nope") is True
    assert any("LLM_MAX_REQUEST_PER_MINUTE" in o for o in ui.outputs)


def test_handle_set_command_model_switches_live(ui):
    assert ui.handle_set_command("/set model gpt-4") is True
    assert ui.model == "gpt-4"
    assert "Model switched to: gpt-4" in "".join(ui.outputs)


def test_handle_set_command_small_model_switches_live(ui):
    assert ui.handle_set_command("/set small_model gpt-4o-mini") is True
    assert ui.small_model == "gpt-4o-mini"
    assert "Small model switched to: gpt-4o-mini" in "".join(ui.outputs)


def test_handle_set_command_multimodal_model_switches_live(ui):
    assert ui.handle_set_command("/set multimodal_model gemini-flash") is True
    assert ui.multimodal_model == "gemini-flash"
    assert "Multimodal model switched to: gemini-flash" in "".join(ui.outputs)


def test_handle_set_command_requires_value(ui):
    assert ui.handle_set_command("/set LLM_MODEL") is True
    assert any("Value required" in o for o in ui.outputs)


def test_handle_set_command_bare_warns_usage(ui):
    assert ui.handle_set_command("/set") is True
    assert any("name and value required" in o.lower() for o in ui.outputs)


def test_handle_set_command_bare_ignored_while_thinking(ui):
    """`/set` is registered run-while-thinking=False, so the bare form must be
    unavailable during a turn exactly like `NAME VALUE` -- it must not jump
    ahead of the thinking guard and consume the input (round-3 review)."""
    ui.is_thinking = True
    assert ui.handle_set_command("/set") is False


def test_handle_set_command_refreshes_live_command_aliases(ui, monkeypatch):
    """A `/set` that changes an alias list must reach the running session.

    `UIConfig` snapshots `LLM_UI_COMMAND_*` when the session is built, so without
    a refresh the command reports success while the session keeps matching the
    old aliases (round-3 review).
    """
    monkeypatch.setenv("ZRB_LLM_UI_COMMAND_SET", "/set")
    assert ui.handle_set_command("/set LLM_UI_COMMAND_SET /set, /configure") is True
    assert CFG.LLM_UI_COMMAND_SET == ["/set", "/configure"]
    assert ui.ui_config.set_commands == ["/set", "/configure"]


def test_handle_toggle_plan_command(ui):
    assert ui.handle_toggle_plan("/plan") is True
    assert ui.plan_mode_active is True
    assert "PLAN MODE: On" in "".join(ui.outputs)
    assert ui.handle_toggle_plan("/plan") is True
    assert ui.plan_mode_active is False
    assert "PLAN MODE: Off" in "".join(ui.outputs)


def test_handle_toggle_plan_command_unrelated_text(ui):
    assert ui.handle_toggle_plan("just a message") is False


def test_handle_yolo_selective_tools(ui):
    assert ui.handle_toggle_yolo("/yolo Write,Edit") is True
    assert ui.yolo == frozenset({"Write", "Edit"})
    # A tool list that parses to nothing leaves yolo untouched but still
    # consumes the input.
    ui.yolo = True
    assert ui.handle_toggle_yolo("/yolo ,") is True
    assert ui.yolo is True


@pytest.mark.asyncio
async def test_handle_exec_command(ui):
    assert ui.handle_exec_command("/exec echo hello") is True
    ui.message_queue.get_nowait()  # drain the enqueued job

    await ui.run_shell_command("echo hello")

    assert "hello" in "".join(ui.outputs)
    assert "successfully" in "".join(ui.outputs)


def test_handle_exec_command_queues_on_the_multi_ui_shared_queue(ui):
    """Under a MultiUI the exec waits its turn behind LLM turns on the shared
    queue, not on the child's own queue."""
    from zrb.llm.ui.multi_ui import MultiUI

    multi_ui = MultiUI([ui])

    assert ui.handle_exec_command("/exec echo hello") is True

    assert multi_ui.message_queue.qsize() == 1
    assert ui.message_queue.qsize() == 0


def test_handle_exec_command_ignored_while_thinking(ui):
    ui.is_thinking = True
    assert ui.handle_exec_command("/exec echo hello") is False
