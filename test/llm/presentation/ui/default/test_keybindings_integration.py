"""A submitted line, driven through the real command stack: it runs a command
or it reaches the LLM, and nothing else.

The double here composes the real `BaseUICommands`, `UIKeybindings` and
`UIMessageEditing` instead of mocking them, so what these pin is the wiring the
mocked tests cannot see: `>` is a configured command token and must run the
redirect handler rather than be answered, a command is held while the model is
thinking, and `/btw` gets through that hold because it is a run-while-thinking
command.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from prompt_toolkit.key_binding import KeyBindings

from zrb.llm.capabilities.hook.contracts.interface import HookEvent
from zrb.llm.presentation.ui.base.commands import BaseUICommands
from zrb.llm.presentation.ui.default.keybindings import UIKeybindings
from zrb.llm.presentation.ui.default.message_editing import UIMessageEditing

from .keybindings_support import create_mock_event, trigger_binding


class IntegrationUI:
    """`BaseUICommands`, `UIKeybindings` and `UIMessageEditing` are all
    composed (not inherited): their handlers read state through the UI
    reference, so `self._cmds`/`self._keybindings`/`self._message_editing`
    plus the `__getattr__` fallback below keep `self.classify_input(...)` /
    `self.schedule_command(...)` working exactly as before."""

    display = input = tools = property(lambda self: self)

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
        self.plan_commands, self.sandbox_commands = ["/plan"], ["/sandbox"]
        self.summarize_commands = ["/summarize"]
        self.copy_commands, self.judge_commands = [], ["/judge"]
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
