"""A submitted message hushes the voice.

A reply arrives twice: as text and read aloud. The text can be read and
answered in seconds while the voice is still on its first paragraph, so a
submission means the voice is describing a turn the user has already moved
past. It is cut rather than allowed to finish — the same hush a barge-in does
from the microphone, reached from the keyboard too (ADR-0103, revised).
"""

from unittest.mock import MagicMock, patch

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.ui.base.ui import BaseUI


class ConcreteUI(BaseUI):
    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        pass

    async def ask_user(self, prompt: str) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0


@pytest.fixture
def base_ui():
    return ConcreteUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(hook_manager=None, active_hook_manager=None),
        history_manager=MagicMock(),
    )


def test_a_submitted_message_hushes_the_voice(base_ui):
    with patch("zrb.llm.speech.feature.interrupt_speech") as hush:
        base_ui.submit_message("never mind, look at this instead")

    hush.assert_called_once_with()


def test_the_message_is_still_queued_after_the_hush(base_ui):
    """A hush quiets the voice; it does not swallow the message or cancel the
    turn — the user's words have to be read."""
    with patch("zrb.llm.speech.feature.interrupt_speech"):
        base_ui.submit_message("keep going, but with tests")

    assert base_ui.queued_message_count == 1


def test_a_child_ui_leaves_the_hush_to_its_parent(base_ui):
    """A child delegates the submission to the `MultiUI`, which is the one that
    queues it; hushing from both would interrupt twice for one message."""
    parent = MagicMock()
    base_ui.multi_ui_parent = parent

    with patch("zrb.llm.speech.feature.interrupt_speech") as hush:
        base_ui.submit_user_message(base_ui.llm_task, "one message")

    assert hush.call_count == 0
    parent.submit_user_message.assert_called_once()


def test_submitting_with_speech_off_is_harmless(base_ui):
    """The real `interrupt_speech`, not a mock: no speech session registered, so
    a submission must not raise on its way to the queue."""
    base_ui.submit_message("nothing is being read aloud")

    assert base_ui.queued_message_count == 1
