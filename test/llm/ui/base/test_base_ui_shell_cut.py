"""Ctrl+G also tells the run's shell to step aside.

Delivering the message is not enough on its own: the model reads it at the next
model request, and that request is assembled after the running tool returns. A
long `Shell` call is what can still keep the message waiting, so the explicit
send-now cuts the run's signal as well.
"""

from unittest.mock import MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.input_source import DICTATION_INPUT
from zrb.llm.shell_cut import ShellCutSignal
from zrb.llm.ui.base.message_queue import QueuedMessage
from zrb.llm.ui.base.queue_delivery import DeliveryOutcome
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.trigger import TriggerReply


class _CutUI(BaseUI):
    def __init__(self, **kwargs):
        self.outputs = []
        super().__init__(**kwargs)

    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        self.outputs.append(sep.join(str(v) for v in values))

    async def ask_user(
        self, prompt: str, output_to_parent: str = "", agent_id: str | None = None
    ) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0

    async def run_async(self) -> str:
        return self.last_output


def _entry(text):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind="message", run=run)


@pytest.fixture
def cut_ui():
    return _CutUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(hook_manager=None, active_hook_manager=None),
        history_manager=MagicMock(),
    )


def test_send_now_cuts_the_runs_shell_so_the_message_is_read_this_turn(cut_ui):
    signal = ShellCutSignal()
    cut_ui.active_run_context = MagicMock()
    cut_ui.shell_cut_signal = signal
    cut_ui.message_queue.put_nowait(_entry("look at this"))

    with patch.object(cut_ui, "redraw_echoes"):
        report = cut_ui.send_queued_messages_now()

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    assert signal.generation == 1


def test_speech_does_not_cut_the_runs_shell(cut_ui):
    """A spoken message never asks the turn to hurry up, so the command it is
    waiting on keeps running (`triggers.py` submits with may_interrupt=False)."""
    signal = ShellCutSignal()
    cut_ui.active_run_context = MagicMock()
    cut_ui.shell_cut_signal = signal

    with patch.object(cut_ui, "append_to_output"):
        cut_ui.submit_message_now("spoken", DICTATION_INPUT, may_interrupt=False)

    assert signal.generation == 0


def test_a_voice_first_session_can_let_speech_move_the_shell(cut_ui):
    """`LLM_VOICE_MOVES_SHELL` is what a hands-free session turns on; the turn
    is still never interrupted."""
    signal = ShellCutSignal()
    cut_ui.active_run_context = MagicMock()
    cut_ui.shell_cut_signal = signal
    cancelled = []
    with (
        patch.object(cut_ui, "append_to_output"),
        patch.object(cut_ui, "cancel_current_turn", side_effect=cancelled.append),
    ):
        cut_ui.submit_message_now(
            "spoken", DICTATION_INPUT, may_interrupt=False, move_shell=True
        )

    assert signal.generation == 1
    assert cancelled == [], "moving a command must not cancel the turn"


def _trigger_yielding(*items):
    async def factory():
        for item in items:
            yield item

    return factory


@pytest.mark.asyncio
async def test_a_spoken_reply_moves_the_shell_only_when_the_setting_says_so(
    cut_ui, monkeypatch
):
    """The trigger is where the setting becomes a decision."""
    moved: list[object] = []

    def fake_send_now(text, source=None, may_interrupt=True, move_shell=None):
        moved.append(move_shell)

    monkeypatch.setattr(cut_ui, "submit_message_now", fake_send_now)
    await cut_ui.trigger_loop(
        _trigger_yielding(TriggerReply("open the file", send_now=True))
    )
    assert moved == [None], "the keyword is only passed when it is asked for"

    monkeypatch.setattr(CFG, "LLM_VOICE_MOVES_SHELL", True, raising=False)
    await cut_ui.trigger_loop(
        _trigger_yielding(TriggerReply("open the file", send_now=True))
    )
    assert moved == [None, True]


@pytest.mark.asyncio
async def test_an_override_of_the_older_signature_still_receives_a_spoken_message(
    cut_ui, monkeypatch
):
    """A custom UI that predates `move_shell` overrides `submit_message_now`
    with the old signature; with the feature off it must still get the words
    rather than a `TypeError` the trigger loop swallows."""
    sent: list[tuple[str, bool]] = []

    def older_send_now(text, source=None, may_interrupt=True):
        sent.append((text, may_interrupt))

    monkeypatch.setattr(cut_ui, "submit_message_now", older_send_now)

    await cut_ui.trigger_loop(
        _trigger_yielding(TriggerReply("open the file", send_now=True))
    )

    assert sent == [("open the file", False)]
