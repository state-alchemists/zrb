from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prompt_toolkit.key_binding import KeyBindings

from zrb.llm.hook.interface import HookEvent
from zrb.llm.ui.default.keybindings_mixin import KeybindingsMixin


class MockUI(KeybindingsMixin):
    def __init__(self):
        self._background_tasks = set()
        self._pending_attachments = []
        self._conversation_session_name = "test_session"
        self._running_llm_task = None
        self._is_thinking = False

        self._input_field = MagicMock()
        self._output_field = MagicMock()

        self.outputs = []

        # Mocks for BaseUI methods
        self._cancel_pending_confirmations = MagicMock()
        self.execute_hook = MagicMock()
        self.append_to_output = MagicMock(side_effect=lambda x: self.outputs.append(x))
        self.invalidate_ui = MagicMock()
        self.toggle_yolo = MagicMock()
        self._submit_user_message = MagicMock()
        self.schedule_command = MagicMock()
        self.classify_input = MagicMock(return_value="message")

        # Mocks for CommandsMixin methods
        self._handle_btw_command = MagicMock(return_value=False)
        self._handle_toggle_yolo = MagicMock(return_value=False)
        self._handle_exit_command = MagicMock(return_value=False)
        self._handle_info_command = MagicMock(return_value=False)
        self._handle_save_command = MagicMock(return_value=False)
        self._handle_load_command = MagicMock(return_value=False)
        self._handle_rewind_command = MagicMock(return_value=False)
        self._handle_redirect_command = MagicMock(return_value=False)
        self._handle_attach_command = MagicMock(return_value=False)
        self._handle_set_model_command = MagicMock(return_value=False)
        self._handle_exec_command = MagicMock(return_value=False)
        self._handle_custom_command = MagicMock(return_value=False)

        # Mock for confirmation handling
        self._handle_confirmation = MagicMock(return_value=False)


@pytest.fixture
def mock_ui():
    return MockUI()


@pytest.fixture
def key_bindings():
    return KeyBindings()


@pytest.fixture
def setup_bindings(mock_ui, key_bindings):
    llm_task = MagicMock()
    mock_ui.setup_app_keybindings(key_bindings, llm_task)
    return key_bindings


def create_mock_event(text=""):
    event = MagicMock()
    event.app.layout.has_focus = MagicMock(return_value=True)
    event.app.layout.focus = MagicMock()

    event.app.current_buffer.text = text
    event.app.current_buffer.selection_state = None
    event.app.current_buffer.copy_selection = MagicMock(return_value="copied_text")
    event.app.current_buffer.exit_selection = MagicMock()
    event.app.current_buffer.reset = MagicMock()
    event.app.current_buffer.append_to_history = MagicMock()
    event.app.current_buffer.insert_text = MagicMock()
    event.app.current_buffer.delete_before_cursor = MagicMock()
    event.app.current_buffer.cursor_position = len(text)

    event.current_buffer = event.app.current_buffer

    event.app.clipboard = MagicMock()
    event.app.clipboard.set_data = MagicMock()
    event.app.clipboard.get_data = MagicMock(return_value="pasted_text")

    event.app.exit = MagicMock()
    return event


def trigger_binding(key_bindings, key, event):
    bindings = key_bindings.get_bindings_for_keys((key,))
    if not bindings:
        return False
    # Execute the last added binding for these keys (similar to prompt_toolkit behavior)
    bindings[-1].handler(event)
    return True


def test_f6_binding_focus_output(mock_ui, setup_bindings):
    event = create_mock_event()
    event.app.layout.has_focus.return_value = True
    trigger_binding(setup_bindings, "f6", event)
    event.app.layout.focus.assert_called_with(mock_ui._output_field)


def test_f6_binding_focus_input(mock_ui, setup_bindings):
    event = create_mock_event()
    event.app.layout.has_focus.return_value = False
    trigger_binding(setup_bindings, "f6", event)
    event.app.layout.focus.assert_called_with(mock_ui._input_field)


def test_ctrl_c_selection(mock_ui, setup_bindings):
    event = create_mock_event()
    event.app.current_buffer.selection_state = True
    trigger_binding(setup_bindings, "c-c", event)
    event.app.clipboard.set_data.assert_called_with("copied_text")
    event.app.current_buffer.exit_selection.assert_called_once()
    assert not mock_ui._cancel_pending_confirmations.called


def test_ctrl_c_text_present(mock_ui, setup_bindings):
    event = create_mock_event("some text")
    trigger_binding(setup_bindings, "c-c", event)
    event.app.current_buffer.reset.assert_called_once()
    assert not mock_ui._cancel_pending_confirmations.called


def test_ctrl_c_empty(mock_ui, setup_bindings):
    event = create_mock_event("")

    # Setup running task
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_ui._running_llm_task = mock_task

    trigger_binding(setup_bindings, "c-c", event)

    mock_ui._cancel_pending_confirmations.assert_called_once()
    mock_task.cancel.assert_called_once()
    assert "\n<Esc> Canceled" in mock_ui.outputs
    mock_ui.execute_hook.assert_called_with(
        HookEvent.STOP,
        {"reason": "ctrl_c", "session": "test_session"},
    )
    event.app.exit.assert_called_once()


def test_escape_binding(mock_ui, setup_bindings):
    event = create_mock_event()

    # Setup running task
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_ui._running_llm_task = mock_task

    trigger_binding(setup_bindings, "escape", event)

    mock_ui._cancel_pending_confirmations.assert_called_once()
    mock_task.cancel.assert_called_once()
    mock_ui.execute_hook.assert_called_with(
        HookEvent.STOP,
        {"reason": "escape", "session": "test_session"},
    )
    assert "\n<Esc> Canceled" in mock_ui.outputs


def test_ctrl_y_binding(mock_ui, setup_bindings):
    event = create_mock_event()
    trigger_binding(setup_bindings, "c-y", event)
    mock_ui.toggle_yolo.assert_called_once()


def test_ctrl_j_binding(mock_ui, setup_bindings):
    event = create_mock_event()
    trigger_binding(setup_bindings, "c-j", event)
    event.current_buffer.insert_text.assert_called_with("\n")


def test_enter_empty_text(mock_ui, setup_bindings):
    event = create_mock_event("   ")
    trigger_binding(setup_bindings, "c-m", event)
    assert not mock_ui._submit_user_message.called


def test_enter_handle_multiline(mock_ui, setup_bindings):
    event = create_mock_event("line1\\")
    trigger_binding(setup_bindings, "c-m", event)
    event.current_buffer.delete_before_cursor.assert_called_with(count=1)
    event.current_buffer.insert_text.assert_called_with("\n")
    assert not mock_ui._submit_user_message.called


def test_enter_handle_confirmation(mock_ui, setup_bindings):
    event = create_mock_event("yes")
    mock_ui._handle_confirmation.return_value = True
    trigger_binding(setup_bindings, "c-m", event)
    assert not mock_ui._submit_user_message.called


def test_enter_thinking_command_routes_even_while_thinking(mock_ui, setup_bindings):
    # Run-while-thinking commands (/btw, YOLO toggle) dispatch regardless of
    # the thinking state. Commands are not appended to input history (main
    # never recalled recognized commands).
    event = create_mock_event("/btw hello")
    mock_ui.classify_input.return_value = "thinking_command"
    mock_ui._is_thinking = True
    trigger_binding(setup_bindings, "c-m", event)
    # Scheduled unguarded so it never blocks / is blocked by another command.
    mock_ui.schedule_command.assert_called_once_with("/btw hello", guarded=False)
    event.current_buffer.reset.assert_called_once()
    assert not event.current_buffer.append_to_history.called
    assert not mock_ui._submit_user_message.called


def test_enter_command_routes_to_dispatch(mock_ui, setup_bindings):
    # A recognized command (any token, e.g. ">" redirect) goes through the
    # hook-wrapped async dispatch — never submitted to the LLM directly.
    # Guards the regression where ">" redirect was swallowed.
    event = create_mock_event("> ~/coba.txt")
    mock_ui.classify_input.return_value = "command"
    trigger_binding(setup_bindings, "c-m", event)
    mock_ui.schedule_command.assert_called_once_with("> ~/coba.txt")
    event.current_buffer.reset.assert_called_once()
    assert not mock_ui._submit_user_message.called


def test_enter_command_gated_while_thinking(mock_ui, setup_bindings):
    # A non-thinking command typed while the LLM is responding is held (not
    # dispatched, not submitted, buffer kept) — matches main.
    event = create_mock_event("/save x")
    mock_ui.classify_input.return_value = "command"
    mock_ui._is_thinking = True
    trigger_binding(setup_bindings, "c-m", event)
    assert not mock_ui.schedule_command.called
    assert not mock_ui._submit_user_message.called
    assert not event.current_buffer.reset.called


def test_enter_message_thinking(mock_ui, setup_bindings):
    event = create_mock_event("hello")
    mock_ui.classify_input.return_value = "message"
    mock_ui._is_thinking = True
    trigger_binding(setup_bindings, "c-m", event)
    assert not mock_ui._submit_user_message.called
    assert not mock_ui.schedule_command.called


def test_enter_submit_message(mock_ui, setup_bindings):
    event = create_mock_event("hello world")
    mock_ui.classify_input.return_value = "message"
    trigger_binding(setup_bindings, "c-m", event)
    event.current_buffer.append_to_history.assert_called_once()
    mock_ui._submit_user_message.assert_called_once()
    event.current_buffer.reset.assert_called_once()


@pytest.mark.asyncio
async def test_ctrl_v_image_found(mock_ui, setup_bindings):
    event = create_mock_event()

    with patch(
        "zrb.llm.util.clipboard.get_clipboard_image", new_callable=AsyncMock
    ) as mock_get_img:
        mock_get_img.return_value = b"fake_image_data"
        trigger_binding(setup_bindings, "c-v", event)

        # Wait for background task
        assert len(mock_ui._background_tasks) == 1
        await list(mock_ui._background_tasks)[0]

        assert len(mock_ui._pending_attachments) == 1
        assert mock_ui._pending_attachments[0].media_type == "image/png"
        mock_ui.invalidate_ui.assert_called_once()


@pytest.mark.asyncio
async def test_ctrl_v_no_image_has_hint(mock_ui, setup_bindings):
    event = create_mock_event()

    with patch(
        "zrb.llm.util.clipboard.get_clipboard_image", new_callable=AsyncMock
    ) as mock_get_img:
        with patch("zrb.llm.util.clipboard.missing_tool_hint") as mock_hint:
            mock_get_img.return_value = None
            mock_hint.return_value = "Missing tool hint"

            trigger_binding(setup_bindings, "c-v", event)

            # Wait for background task
            assert len(mock_ui._background_tasks) == 1
            await list(mock_ui._background_tasks)[0]

            assert len(mock_ui._pending_attachments) == 0
            mock_ui.invalidate_ui.assert_called_once()
            assert any("Missing tool hint" in out for out in mock_ui.outputs)


@pytest.mark.asyncio
async def test_ctrl_v_no_image_no_hint(mock_ui, setup_bindings):
    event = create_mock_event()

    with patch(
        "zrb.llm.util.clipboard.get_clipboard_image", new_callable=AsyncMock
    ) as mock_get_img:
        with patch("zrb.llm.util.clipboard.missing_tool_hint") as mock_hint:
            with patch("prompt_toolkit.application.get_app") as mock_get_app:
                mock_get_img.return_value = None
                mock_hint.return_value = None

                app_mock = MagicMock()
                mock_get_app.return_value = app_mock

                trigger_binding(setup_bindings, "c-v", event)

                # Wait for background task
                assert len(mock_ui._background_tasks) == 1
                await list(mock_ui._background_tasks)[0]

                app_mock.layout.focus.assert_called_with(mock_ui._input_field)
                mock_ui._input_field.buffer.paste_clipboard_data.assert_called_with(
                    "pasted_text"
                )


# --- Integration: real keybinding + real classification/dispatch/handlers ---
#
# These drive the actual Enter binding through CommandsMixin's real
# classify_input -> schedule_command -> dispatch_command -> _run_command_chain
# -> _handle_* path. Only leaf IO (LLM submit, hook manager, the btw side-query)
# is stubbed, so the routing regressions — especially a non-"/" ">" redirect
# token — are caught end-to-end rather than behind mocked routing.

from zrb.llm.ui.base.commands_mixin import CommandsMixin  # noqa: E402


class IntegrationUI(KeybindingsMixin, CommandsMixin):
    def __init__(self):
        self._exit_commands = ["/exit"]
        self._info_commands = ["/help"]
        self._save_commands = ["/save"]
        self._load_commands = ["/load"]
        self._rewind_commands = ["/rewind"]
        self._redirect_output_commands = [">"]  # non-"/" token (the regression)
        self._attach_commands = ["/attach"]
        self._yolo_toggle_commands = ["/yolo"]
        self._set_model_commands = ["/model"]
        self._exec_commands = ["/exec"]
        self._btw_commands = ["/btw"]
        self._plan_commands = ["/plan"]
        self._summarize_commands = ["/summarize"]
        self._copy_commands = []
        self._custom_commands = []
        self._is_thinking = False
        self._background_tasks = set()
        self._conversation_session_name = "default"
        self._snapshot_manager = None
        self._llm_task = MagicMock()
        self.last_output = "AI RESPONSE TEXT"
        self._input_field = MagicMock()
        self._output_field = MagicMock()
        self.submitted = []
        self.outputs = []
        self.btw_questions = []
        self.execute_hook = MagicMock()
        self.execute_hook_blocking = AsyncMock(return_value=[])
        # Leaf collaborators only.
        self._handle_confirmation = MagicMock(return_value=False)

    def append_to_output(self, text, end="\n"):
        self.outputs.append(str(text))

    def _submit_user_message(self, task, text):
        self.submitted.append(text)

    async def _stream_btw_response(self, task, question):
        self.btw_questions.append(question)


@pytest.fixture
def integration_ui():
    ui = IntegrationUI()
    kb = KeyBindings()
    ui.setup_app_keybindings(kb, ui._llm_task)
    return ui, kb


async def _drain(ui):
    """Await every scheduled task, including ones spawned during dispatch."""
    while ui._background_tasks:
        task = next(iter(ui._background_tasks))
        try:
            await task
        except Exception:
            pass
        ui._background_tasks.discard(task)


@pytest.mark.asyncio
async def test_integration_redirect_token_writes_file(integration_ui, tmp_path):
    # The bug that started this: ">" is a configured (non-"/") command token.
    # Driving the real keybinding must run the redirect handler, not the LLM.
    ui, kb = integration_ui
    out = tmp_path / "sub" / "out.txt"
    event = create_mock_event(f"> {out}")

    trigger_binding(kb, "c-m", event)
    assert len(ui._background_tasks) == 1
    await _drain(ui)

    assert out.read_text() == "AI RESPONSE TEXT"  # redirect actually ran
    assert ui.submitted == []  # NOT forwarded to the LLM
    assert ui.execute_hook_blocking.call_args.args[0] == HookEvent.PRE_COMMAND
    assert ui.execute_hook.call_args.args[0] == HookEvent.POST_COMMAND


def test_integration_plain_message_goes_to_llm(integration_ui):
    ui, kb = integration_ui
    event = create_mock_event("explain this code")

    trigger_binding(kb, "c-m", event)

    assert ui.submitted == ["explain this code"]
    assert not ui._background_tasks  # no command dispatched, no hooks


def test_integration_redirect_gated_while_thinking(integration_ui, tmp_path):
    ui, kb = integration_ui
    ui._is_thinking = True
    out = tmp_path / "out.txt"
    event = create_mock_event(f"> {out}")

    trigger_binding(kb, "c-m", event)

    assert not ui._background_tasks  # command held while thinking
    assert ui.submitted == []
    assert not out.exists()


@pytest.mark.asyncio
async def test_integration_slash_command_runs(integration_ui):
    ui, kb = integration_ui
    event = create_mock_event("/help")

    trigger_binding(kb, "c-m", event)
    await _drain(ui)

    assert any("Keyboard Shortcuts" in o for o in ui.outputs)  # help printed
    assert ui.submitted == []
    assert ui.execute_hook.call_args.args[0] == HookEvent.POST_COMMAND


@pytest.mark.asyncio
async def test_integration_btw_runs_while_thinking(integration_ui):
    # /btw is a run-while-thinking command: it dispatches and runs even while
    # the LLM is responding.
    ui, kb = integration_ui
    ui._is_thinking = True
    event = create_mock_event("/btw are you there")

    trigger_binding(kb, "c-m", event)
    assert len(ui._background_tasks) >= 1
    await _drain(ui)

    assert ui.btw_questions == ["are you there"]
    assert ui.submitted == []
