from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prompt_toolkit.clipboard import ClipboardData
from prompt_toolkit.key_binding import KeyBindings

from zrb.llm.hook.interface import HookEvent
from zrb.llm.ui.base.message_queue import MessageQueue
from zrb.llm.ui.default.agent_picker import UIAgentPicker
from zrb.llm.ui.default.keybindings import UIKeybindings
from zrb.llm.ui.default.message_editing import UIMessageEditing


class MockUI:
    """Stand-in UI composing the real `UIKeybindings`, `UIMessageEditing`
    and `UIAgentPicker`. Each part reaches this object's state via
    `self._ui`, using only public names — matching the real default `UI`.
    State that lives inside the composed parts themselves (`queued_edit_entry`/
    `queued_edit_draft` on `UIMessageEditing`, `viewing_agent_id`/
    `saved_main_output` on `UIAgentPicker`) is reached the same way tests reach
    it: through the part's own public property, via `__getattr__` below.
    """

    def __init__(self):
        self.background_tasks = set()
        self.pending_attachments = []
        self.conversation_session_name = "test_session"
        self.running_llm_task = None
        self.is_thinking = False

        self.input_field = MagicMock()
        self.output_field = MagicMock()
        self.input_field.buffer = MagicMock(text="", cursor_position=0)

        self.outputs = []

        self._message_queue = MessageQueue()
        self.edit_queued_message = MagicMock(return_value=True)

        self._keybindings = UIKeybindings(self)
        self._message_editing = UIMessageEditing(self)
        # Sub-agent picker + live view (see UIAgentPicker). Mirrors the real
        # default `UI` composition so Down Arrow's picker trigger works.
        self._agent_picker = UIAgentPicker(self)
        self._agent_picker.init_agent_picker_state()

        # Mocks for BaseUI methods
        self.cancel_pending_confirmations = MagicMock()
        self.execute_hook = MagicMock()
        self.append_to_output = MagicMock(side_effect=lambda x: self.outputs.append(x))
        self.invalidate_ui = MagicMock()
        self.toggle_yolo = MagicMock()
        self.toggle_collapsible_block = MagicMock()
        self.cycle_mode = MagicMock()
        self.submit_user_message = MagicMock()
        self.schedule_command = MagicMock()
        self.classify_input = MagicMock(return_value="message")

        # Mocks for BaseUICommands methods
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
        self.handle_confirmation = MagicMock(return_value=False)

    @property
    def effective_message_queue(self):
        return self._message_queue

    @property
    def output_text(self):
        return self.output_field.text

    def set_output_text(self, text):
        self.output_field.text = text

    def setup_app_keybindings(self, app_keybindings, llm_task):
        return self._keybindings.setup_app_keybindings(app_keybindings, llm_task)

    # `__getattr__` below handles reads of state that lives on a composed
    # part, but not writes (Python's default `__setattr__` would just shadow
    # it with a same-named instance attribute on this mock instead). These
    # forward both directions, through the part's own public property.

    @property
    def queued_edit_entry(self):
        return self._message_editing.queued_edit_entry

    @queued_edit_entry.setter
    def queued_edit_entry(self, value):
        self._message_editing.queued_edit_entry = value

    @property
    def queued_edit_draft(self):
        return self._message_editing.queued_edit_draft

    @queued_edit_draft.setter
    def queued_edit_draft(self, value):
        self._message_editing.queued_edit_draft = value

    @property
    def viewing_agent_id(self):
        return self._agent_picker.viewing_agent_id

    @viewing_agent_id.setter
    def viewing_agent_id(self, value):
        self._agent_picker.viewing_agent_id = value

    @property
    def saved_main_output(self):
        return self._agent_picker.saved_main_output

    @saved_main_output.setter
    def saved_main_output(self, value):
        self._agent_picker.saved_main_output = value

    def __getattr__(self, name):
        for part_attr in ("_message_editing", "_agent_picker", "_keybindings"):
            part = self.__dict__.get(part_attr)
            if part is not None and hasattr(part, name):
                return getattr(part, name)
        raise AttributeError(name)


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
    event.app.current_buffer.copy_selection = MagicMock(
        return_value=ClipboardData("copied_text")
    )
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
    # Execute the last binding whose filter passes — prompt_toolkit's own
    # key processor (its match-finding step) evaluates `binding.filter()` at
    # match time even though the raw registry's `get_bindings_for_keys`
    # returns inactive bindings too. Last-match-wins mirrors prompt_toolkit's
    # priority order.
    for binding in reversed(bindings):
        if binding.filter():
            binding.handler(event)
            return True
    return False


from zrb.llm.ui.base.commands import BaseUICommands  # noqa: E402


class IntegrationUI:
    """`BaseUICommands`, `UIKeybindings` and `UIMessageEditing` are all
    composed (not inherited): their handlers read state through the UI
    reference, so `self._cmds`/`self._keybindings`/`self._message_editing`
    plus the `__getattr__` fallback below keep `self.classify_input(...)` /
    `self.schedule_command(...)` working exactly as before."""

    def __init__(self):
        self.exit_commands = ["/exit"]
        self.info_commands = ["/help"]
        self.save_commands = ["/save"]
        self.load_commands = ["/load"]
        self.rewind_commands = ["/rewind"]
        self.redirect_output_commands = [">"]  # non-"/" token (the regression)
        self.attach_commands = ["/attach"]
        self.yolo_toggle_commands = ["/yolo"]
        self.set_model_commands = ["/model"]
        self.set_commands = ["/set"]
        self.exec_commands = ["/exec"]
        self.btw_commands = ["/btw"]
        self.plan_commands = ["/plan"]
        self.summarize_commands = ["/summarize"]
        self.copy_commands = []
        self.custom_commands = []
        self.is_thinking = False
        self.background_tasks = set()
        self.conversation_session_name = "default"
        self.snapshot_manager = None
        self.llm_task = MagicMock()
        self.last_output = "AI RESPONSE TEXT"
        self.input_field = MagicMock()
        self.output_field = MagicMock()
        self.submitted = []
        self.outputs = []
        self.btw_questions = []
        self.execute_hook = MagicMock()
        self.execute_hook_blocking = AsyncMock(return_value=[])
        # Leaf collaborators only.
        self.handle_confirmation = MagicMock(return_value=False)

        self._cmds = BaseUICommands(self)
        self._keybindings = UIKeybindings(self)
        self._message_editing = UIMessageEditing(self)

    def __getattr__(self, name):
        cmds = self.__dict__.get("_cmds")
        if cmds is not None:
            for collaborator_attr in ("", "conversation", "models", "exec"):
                holder = getattr(cmds, collaborator_attr) if collaborator_attr else cmds
                if hasattr(holder, name):
                    return getattr(holder, name)
        for part_attr in ("_keybindings", "_message_editing"):
            part = self.__dict__.get(part_attr)
            if part is not None and hasattr(part, name):
                return getattr(part, name)
        raise AttributeError(name)

    def setup_app_keybindings(self, app_keybindings, llm_task):
        return self._keybindings.setup_app_keybindings(app_keybindings, llm_task)

    def append_to_output(self, text, end="\n"):
        self.outputs.append(str(text))

    def submit_user_message(self, task, text):
        self.submitted.append(text)

    async def stream_btw_response(self, task, question):
        self.btw_questions.append(question)


@pytest.fixture
def integration_ui():
    ui = IntegrationUI()
    kb = KeyBindings()
    ui.setup_app_keybindings(kb, ui.llm_task)
    return ui, kb


async def _drain(ui):
    """Await every scheduled task, including ones spawned during dispatch."""
    while ui.background_tasks:
        task = next(iter(ui.background_tasks))
        try:
            await task
        except Exception:
            pass
        ui.background_tasks.discard(task)


@pytest.mark.asyncio
async def test_ctrl_v_no_image_no_hint(mock_ui, setup_bindings):
    event = create_mock_event()

    with patch(
        "zrb.util.clipboard.get_clipboard_image", new_callable=AsyncMock
    ) as mock_get_img:
        with patch("zrb.util.clipboard.missing_tool_hint") as mock_hint:
            with patch("prompt_toolkit.application.get_app") as mock_get_app:
                mock_get_img.return_value = None
                mock_hint.return_value = None

                app_mock = MagicMock()
                mock_get_app.return_value = app_mock

                trigger_binding(setup_bindings, "c-v", event)

                # Wait for background task
                assert len(mock_ui.background_tasks) == 1
                await list(mock_ui.background_tasks)[0]

                app_mock.layout.focus.assert_called_with(mock_ui.input_field)
                mock_ui.input_field.buffer.paste_clipboard_data.assert_called_with(
                    "pasted_text"
                )


@pytest.mark.asyncio
async def test_ctrl_v_refuses_an_image_too_large_to_decode(
    mock_ui, setup_bindings, monkeypatch
):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(buf, format="PNG")
    monkeypatch.setattr("zrb.llm.util.image_scale.MAX_DECODE_PIXELS", 100)
    with patch(
        "zrb.util.clipboard.get_clipboard_image", new_callable=AsyncMock
    ) as mock_get_img:
        mock_get_img.return_value = buf.getvalue()
        trigger_binding(setup_bindings, "c-v", create_mock_event())
        await list(mock_ui.background_tasks)[0]

    assert mock_ui.pending_attachments == []
    assert any("too large to decode safely" in out for out in mock_ui.outputs)


@pytest.mark.asyncio
async def test_integration_redirect_token_writes_file(integration_ui, tmp_path):
    # The bug that started this: ">" is a configured (non-"/") command token.
    # Driving the real keybinding must run the redirect handler, not the LLM.
    ui, kb = integration_ui
    out = tmp_path / "sub" / "out.txt"
    event = create_mock_event(f"> {out}")

    trigger_binding(kb, "c-m", event)
    assert len(ui.background_tasks) == 1
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
    assert not ui.background_tasks  # no command dispatched, no hooks


def test_integration_redirect_gated_while_thinking(integration_ui, tmp_path):
    ui, kb = integration_ui
    ui.is_thinking = True
    out = tmp_path / "out.txt"
    event = create_mock_event(f"> {out}")

    trigger_binding(kb, "c-m", event)

    assert not ui.background_tasks  # command held while thinking
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
    ui.is_thinking = True
    event = create_mock_event("/btw are you there")

    trigger_binding(kb, "c-m", event)
    assert len(ui.background_tasks) >= 1
    await _drain(ui)

    assert ui.btw_questions == ["are you there"]
    assert ui.submitted == []


def _paste(key_bindings, data):
    # lazy: heavy third-party
    from prompt_toolkit.keys import Keys

    event = create_mock_event()
    event.data = data
    trigger_binding(key_bindings, Keys.BracketedPaste, event)
    return event


def test_bracketed_paste_of_a_file_path_attaches_it(mock_ui, setup_bindings, tmp_path):
    image = tmp_path / "pasted-image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    _paste(setup_bindings, f"{image}\r\n")

    mock_ui.input_field.buffer.insert_text.assert_not_called()
    assert len(mock_ui.pending_attachments) == 1
    assert mock_ui.pending_attachments[0].media_type == "image/png"
    assert any("Attached: pasted-image.png" in o for o in mock_ui.outputs)


def test_bracketed_paste_of_an_unreadable_file_reports_it(
    mock_ui, setup_bindings, tmp_path
):
    image = tmp_path / "fake.png"
    image.write_bytes(b"not a png")

    _paste(setup_bindings, str(image))

    mock_ui.input_field.buffer.insert_text.assert_not_called()
    assert mock_ui.pending_attachments == []
    assert any("doesn't look like image/png" in o for o in mock_ui.outputs)


def test_bracketed_paste_of_text_goes_to_the_input_field(mock_ui, setup_bindings):
    # Focus may be on the read-only output pane; the paste still lands in input.
    event = _paste(setup_bindings, "line one\r\nline two\r")

    event.app.layout.focus.assert_called_once_with(mock_ui.input_field)
    mock_ui.input_field.buffer.insert_text.assert_called_once_with(
        "line one\nline two\n"
    )
    event.current_buffer.insert_text.assert_not_called()
    assert mock_ui.pending_attachments == []


def test_bracketed_paste_of_a_pdf_reaches_the_prompt_as_its_text(
    mock_ui, setup_bindings, tmp_path
):
    from zrb.llm.agent.run.prompt_content import get_prompt_content

    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    mock_ui.submit_attachment = MagicMock(
        side_effect=mock_ui.pending_attachments.append
    )

    _paste(setup_bindings, str(pdf))
    with patch("zrb.llm.util.attachment.extract_pdf_text", return_value="report text"):
        content = get_prompt_content("hi", mock_ui.pending_attachments, print)

    mock_ui.submit_attachment.assert_called_once_with(str(pdf))
    assert content == ["hi", "report text"]


def test_bracketed_paste_of_the_same_image_twice_attaches_it_once(
    mock_ui, setup_bindings, tmp_path
):
    image = tmp_path / "pasted-image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    _paste(setup_bindings, str(image))
    _paste(setup_bindings, str(image))

    assert len(mock_ui.pending_attachments) == 1
    assert any("Already attached: pasted-image.png" in o for o in mock_ui.outputs)


def test_bracketed_paste_of_an_image_queued_by_attach_is_not_added(
    mock_ui, setup_bindings, tmp_path
):
    image = tmp_path / "photo.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    mock_ui.pending_attachments.append(str(image))

    _paste(setup_bindings, str(image))

    assert mock_ui.pending_attachments == [str(image)]
    assert any("Already attached: photo.png" in o for o in mock_ui.outputs)
