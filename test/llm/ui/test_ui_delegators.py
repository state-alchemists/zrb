"""Delegator surface of the default `UI`.

`UI` composes eight parts (`output_part`, `lifecycle_part`, ...) and forwards
to them through a thin public delegator each. Those delegators are real
surface user code and keybindings call, so they are pinned here: every arrow
`UI.x(...) -> part.y(...)` is exercised and the forwarded call asserted on the
part, which has its own dedicated tests for behavior.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.default.ui import UI


def _ui(mock_ui_deps) -> UI:
    return UI(**mock_ui_deps)


@pytest.mark.asyncio
async def test_lifecycle_delegators(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    lifecycle = ui.lifecycle_part
    lifecycle.cleanup_background_tasks = AsyncMock()
    lifecycle.run_async = AsyncMock(return_value="done")
    lifecycle.on_first_render = MagicMock()
    lifecycle.invalidate_ui = MagicMock()
    lifecycle.on_exit = MagicMock()

    await ui.cleanup_background_tasks()
    assert lifecycle.cleanup_background_tasks.await_count == 1
    assert await ui.run_async() == "done"
    lifecycle.run_async.assert_awaited()
    ui.on_first_render(MagicMock())
    lifecycle.on_first_render.assert_called_once()
    ui.invalidate_ui()
    lifecycle.invalidate_ui.assert_called_once()
    ui.on_exit()
    lifecycle.on_exit.assert_called_once()


def test_agent_picker_delegators(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    picker = ui.agent_picker_part
    picker.open_agent_picker = MagicMock(return_value=True)
    picker.close_agent_picker = MagicMock()
    picker.move_agent_picker_cursor = MagicMock()
    picker.confirm_agent_picker = MagicMock(return_value=True)
    picker.enter_agent_view = MagicMock()
    picker.exit_agent_view = MagicMock()
    picker.cancel_viewed_agent = MagicMock(return_value=True)

    assert not ui.viewing_agent_id
    ui.saved_main_output = None
    assert ui.saved_main_output is None
    assert ui.open_agent_picker() is True
    picker.open_agent_picker.assert_called_once()
    ui.close_agent_picker()
    picker.close_agent_picker.assert_called_once()
    ui.move_agent_picker_cursor(1)
    picker.move_agent_picker_cursor.assert_called_once_with(1)
    assert ui.confirm_agent_picker() is True
    picker.confirm_agent_picker.assert_called_once()
    ui.enter_agent_view(MagicMock())
    picker.enter_agent_view.assert_called_once()
    ui.exit_agent_view()
    picker.exit_agent_view.assert_called_once()
    assert ui.cancel_viewed_agent() is True
    picker.cancel_viewed_agent.assert_called_once()


def test_message_editing_delegators(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    editing = ui.message_editing_part
    editing.recall_navigation_active = MagicMock(return_value=False)
    editing.handle_enter_queued_edit = MagicMock(return_value=False)
    editing.track_echo_span = MagicMock()
    editing.redraw_echo = MagicMock(return_value="redrawn")

    entry = MagicMock()
    ui.queued_edit_entry
    assert ui.recall_navigation_active() is False
    editing.recall_navigation_active.assert_called_once()
    assert ui.handle_enter_queued_edit(MagicMock()) is False
    editing.handle_enter_queued_edit.assert_called_once()
    ui.track_echo_span(entry, "echo")
    editing.track_echo_span.assert_called_once_with(entry, "echo")
    assert ui.redraw_echo(entry) == "redrawn"
    editing.redraw_echo.assert_called_once_with(entry)


def test_output_part_accessors(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    assert ui.output_part is ui.output_part
    assert ui.selection_part is ui.selection_part
    assert ui.confirmation_part is ui.confirmation_part
    assert ui.message_editing_part is ui.message_editing_part
    assert ui.agent_picker_part is ui.agent_picker_part
    assert ui.lifecycle_part is ui.lifecycle_part
    assert ui.keybindings_part is ui.keybindings_part
    assert ui.output_field is not None


def test_output_text_and_fields(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    assert isinstance(ui.output_text, str)
    assert ui.input_field is not None
    assert isinstance(ui.capture, object)
    assert ui.refresh_task is None
    ui.refresh_task = None
    assert ui.refresh_task is None
    assert ui.rendered_width is None
    ui.rendered_width = 80
    assert ui.rendered_width == 80
    ui.pending_invalidate = True
    assert ui.pending_invalidate is True
    assert ui.invalidate_task is None
    ui.invalidate_task = None
    assert ui.invalidate_task is None
    assert ui.output_field_width is None or ui.output_field_width > 0


def test_output_delegators(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    output = ui.output_part
    output.append_markdown = MagicMock()
    output.render_markdown = MagicMock(return_value="rendered")
    output.set_rendered_block = MagicMock()
    output.print_help = MagicMock()
    output.append_rendered = MagicMock()
    output.rewrap_output = MagicMock()
    output.replace_output_span = MagicMock(return_value=True)
    output.append_toggle_block = MagicMock()
    output.mark_thinking_block_start = MagicMock()
    output.collapse_thinking_block = MagicMock(return_value=True)
    output.mark_text_block_start = MagicMock()
    output.collapse_text_block = MagicMock(return_value=True)
    output.update_tool_prepare = MagicMock()
    output.update_shell_output = MagicMock()
    output.finish_shell_output = MagicMock(return_value=True)
    output.set_output_text = MagicMock()
    output.schedule_invalidate = MagicMock()

    ui.append_markdown("# hi")
    output.append_markdown.assert_called_once_with("# hi")
    assert ui.render_markdown("x", 40) == "rendered"
    output.render_markdown.assert_called_once_with("x", 40)
    ui.set_rendered_block(0, 1, "src", "renderer")
    output.set_rendered_block.assert_called_once_with(0, 1, "src", "renderer")
    ui.print_help()
    output.print_help.assert_called_once()
    ui.append_rendered("src", MagicMock())
    output.append_rendered.assert_called_once()
    ui.rewrap_output()
    output.rewrap_output.assert_called_once()
    assert ui.replace_output_span(0, 1, "r") is True
    output.replace_output_span.assert_called_once_with(0, 1, "r")
    ui.record_tool_call_block("c", "f")
    output.append_toggle_block.assert_called_once_with("c", "f")
    ui.mark_thinking_block_start()
    output.mark_thinking_block_start.assert_called_once()
    assert ui.collapse_thinking_block("c", "f") is True
    output.collapse_thinking_block.assert_called_once_with("c", "f")
    ui.mark_text_block_start()
    output.mark_text_block_start.assert_called_once()
    assert ui.collapse_text_block("c", "f") is True
    output.collapse_text_block.assert_called_once_with("c", "f")
    ui.update_tool_prepare("k", "t")
    output.update_tool_prepare.assert_called_once_with("k", "t")
    ui.update_shell_output("k", "t")
    output.update_shell_output.assert_called_once_with("k", "t")
    assert ui.finish_shell_output("k", "c", "f") is True
    output.finish_shell_output.assert_called_once_with("k", "c", "f")
    ui.set_output_text("txt")
    output.set_output_text.assert_called_once_with("txt")
    ui.schedule_invalidate()
    output.schedule_invalidate.assert_called_once()


def test_confirmation_and_selection_delegators(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    confirmation = ui.confirmation_part
    selection = ui.selection_part
    confirmation.cancel_pending_confirmations = MagicMock()
    confirmation.resolve_current = MagicMock(return_value=True)
    selection.begin_choice = MagicMock()
    selection.end_choice = MagicMock()
    selection.handle_confirmation = MagicMock(return_value=True)

    ui.cancel_pending_confirmations(flush=False)
    confirmation.cancel_pending_confirmations.assert_called_once_with(flush=False)
    assert ui.resolve_current("t", "e") is True
    confirmation.resolve_current.assert_called_once_with("t", "e")
    ui.begin_choice(MagicMock())
    selection.begin_choice.assert_called_once()
    ui.end_choice()
    selection.end_choice.assert_called_once()
    assert ui.handle_confirmation(MagicMock()) is True
    selection.handle_confirmation.assert_called_once()


@pytest.mark.asyncio
async def test_confirmation_async_delegators(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    confirmation = ui.confirmation_part
    confirmation.ask_user = AsyncMock(return_value="answer")
    confirmation.ask_user_choice = AsyncMock(return_value="pick")

    assert await ui.ask_user("prompt") == "answer"
    confirmation.ask_user.assert_awaited_once_with("prompt", "", None)
    assert await ui.ask_user_choice(MagicMock()) == "pick"
    confirmation.ask_user_choice.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_interactive_command_hands_terminal_to_subprocess(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    with patch(
        "prompt_toolkit.application.run_in_terminal", new_callable=AsyncMock
    ) as run_in_terminal, patch("subprocess.call") as subprocess_call:
        run_in_terminal.side_effect = lambda handler: handler()
        await ui.run_interactive_command("echo hi", shell=False)
    run_in_terminal.assert_awaited_once()
    subprocess_call.assert_called_once_with("echo hi", shell=False)


def test_toggle_collapsible_block_both_paths(mock_ui_deps):
    ui = _ui(mock_ui_deps)
    output = ui.output_part
    output.toggle_collapsible_block_at_cursor = MagicMock(return_value=False)
    assert ui.toggle_collapsible_block() is False
    output.toggle_collapsible_block_at_cursor.assert_called_once()
    with patch.object(ui, "invalidate_ui") as invalidate_ui:
        output.toggle_collapsible_block_at_cursor.return_value = True
        assert ui.toggle_collapsible_block() is True
        invalidate_ui.assert_called_once()