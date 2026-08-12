import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.ui.default.confirmation import UIConfirmation


class MockConfirmationUI(UIConfirmation):
    def __init__(self):
        self._confirmation_queue = []
        self._confirmation_output_buffer = []
        self._current_confirmation = None

    def append_to_output(self, text, end="\n"):
        pass

    def invalidate_ui(self):
        pass


class FakeBuffer:
    """Minimal stand-in for a prompt_toolkit `Buffer`."""

    def __init__(self, text="", cursor_position=0):
        self.text = text
        self.cursor_position = cursor_position

    def reset(self):
        self.text = ""
        self.cursor_position = 0


class FakeInputField:
    def __init__(self, text=""):
        self.buffer = FakeBuffer(text)


class DraftConfirmationUI(UIConfirmation):
    """Wires a fake input field so the draft stash/restore paths run."""

    def __init__(self, draft=""):
        self._confirmation_queue = []
        self._confirmation_output_buffer = []
        self._current_confirmation = None
        self._saved_draft = None
        self._input_field = FakeInputField(draft)

    def append_to_output(self, text, end="\n"):
        pass

    def invalidate_ui(self):
        pass


class GuardedConfirmationUI(UIConfirmation):
    """Replicates `UIOutput.append_to_output`'s buffer guard.

    Output appended while a confirmation is pending AND the agent is thinking is
    buffered (to stop main-agent tokens interleaving with a prompt). This is the
    exact condition that previously swallowed the confirmation prompt itself.
    """

    def __init__(self, is_thinking=True):
        self._confirmation_queue = []
        self._confirmation_output_buffer = []
        self._current_confirmation = None
        self._is_thinking = is_thinking
        self.rendered = []

    def append_to_output(self, *values, end="\n", **kwargs):
        content = " ".join(str(v) for v in values) + end
        if self._current_confirmation is not None and self._is_thinking:
            self._confirmation_output_buffer.append(content)
            return
        self.rendered.append(content)

    def invalidate_ui(self):
        pass


@pytest.mark.asyncio
async def test_ask_user_queueing():
    ui = MockConfirmationUI()

    with patch("prompt_toolkit.application.get_app") as mock_get_app:
        # First call becomes current
        task1 = asyncio.create_task(ui.ask_user("prompt 1"))
        await asyncio.sleep(0.01)
        assert ui._current_confirmation is not None

        # Second call is queued
        task2 = asyncio.create_task(ui.ask_user("prompt 2"))
        await asyncio.sleep(0.01)
        assert len(ui._confirmation_queue) == 2  # task1 and task2

        # Submit first answer
        ui.submit_user_answer("answer 1")
        res1 = await task1
        assert res1 == "answer 1"

        # Second call should now be current
        assert ui._current_confirmation is not None

        # Submit second answer
        ui.submit_user_answer("answer 2")
        res2 = await task2
        assert res2 == "answer 2"
        assert ui._current_confirmation is None


@pytest.mark.asyncio
async def test_prompt_renders_while_thinking_not_swallowed_by_buffer():
    """Regression: the confirmation prompt must render even mid-stream.

    `ask_user` must append the prompt *before* marking the confirmation pending;
    otherwise append_to_output's buffer guard (current_confirmation set + thinking)
    swallows the prompt, leaving the user at "waiting for confirmation" with no
    question shown — the AskUserQuestion symptom.
    """
    ui = GuardedConfirmationUI(is_thinking=True)

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("[Q1] Pick one\n  1. A\n  2. B"))
        await asyncio.sleep(0.01)

        # The prompt was rendered, not buffered away.
        assert any("[Q1] Pick one" in chunk for chunk in ui.rendered)
        assert ui._confirmation_output_buffer == []
        # ...and the confirmation is now correctly marked pending.
        assert ui._current_confirmation is not None

        ui.submit_user_answer("1")
        assert await task == "1"


@pytest.mark.asyncio
async def test_queued_prompt_renders_when_activated_while_thinking():
    """A queued prompt must also render (not buffer) when it becomes current."""
    ui = GuardedConfirmationUI(is_thinking=True)

    with patch("prompt_toolkit.application.get_app"):
        task1 = asyncio.create_task(ui.ask_user("first prompt"))
        await asyncio.sleep(0.01)
        task2 = asyncio.create_task(ui.ask_user("second prompt"))
        await asyncio.sleep(0.01)

        ui.submit_user_answer("a1")
        assert await task1 == "a1"

        # Activating the queued confirmation must surface its prompt.
        assert any("second prompt" in chunk for chunk in ui.rendered)
        assert ui._confirmation_output_buffer == []

        ui.submit_user_answer("a2")
        assert await task2 == "a2"


@pytest.mark.asyncio
async def test_main_agent_output_buffers_during_confirmation_then_flushes():
    """Background delegation: prompt shows, main-agent output buffers, then flushes.

    When the main agent runs DelegateToAgentBackground and a sub-agent asks for
    approval, the prompt must display immediately, the main agent's continued
    output must be buffered (not interleaved with the prompt), and the buffered
    output must flush all at once once the user answers. The ask_user reorder
    must preserve this.
    """
    ui = GuardedConfirmationUI(is_thinking=True)

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("[approve?] run tool"))
        await asyncio.sleep(0.01)

        # 1. The prompt renders immediately — UI stops for input.
        assert any("[approve?] run tool" in c for c in ui.rendered)

        # 2. Main agent keeps streaming while the confirmation is pending: buffered.
        ui.append_to_output("main token 1")
        ui.append_to_output("main token 2")
        assert ui._confirmation_output_buffer  # held, not rendered
        assert not any("main token" in c for c in ui.rendered)

        # 3. User answers -> buffered main-agent output flushes all at once.
        ui.submit_user_answer("y")
        assert await task == "y"
        assert any("main token 1" in c for c in ui.rendered)
        assert any("main token 2" in c for c in ui.rendered)
        assert ui._confirmation_output_buffer == []


@pytest.mark.asyncio
async def test_cancel_pending_confirmations():
    ui = MockConfirmationUI()

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)

        ui.cancel_pending_confirmations()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert ui._current_confirmation is None
        assert len(ui._confirmation_queue) == 0


@pytest.mark.asyncio
async def test_draft_stashed_and_cleared_when_confirmation_activates():
    """The half-typed message leaves the field while a confirmation is pending."""
    ui = DraftConfirmationUI(draft="fix the auth bug")

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)

        assert ui._current_confirmation is not None
        assert ui._saved_draft == ("fix the auth bug", 0)
        assert ui._input_field.buffer.text == ""

        ui.submit_user_answer("y")
        assert await task == "y"


@pytest.mark.asyncio
async def test_draft_restored_with_cursor_after_answer():
    """After the confirmation resolves, text and cursor position come back."""
    ui = DraftConfirmationUI(draft="fix the auth bug")
    ui._input_field.buffer.cursor_position = 5

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)
        assert ui._input_field.buffer.text == ""

        ui.submit_user_answer("n")
        assert await task == "n"

        assert ui._saved_draft is None
        assert ui._input_field.buffer.text == "fix the auth bug"
        assert ui._input_field.buffer.cursor_position == 5


@pytest.mark.asyncio
async def test_draft_restored_only_after_queue_drains():
    """Stashed draft survives intermediate confirmations in the queue."""
    ui = DraftConfirmationUI(draft="fix the auth bug")

    with patch("prompt_toolkit.application.get_app"):
        task1 = asyncio.create_task(ui.ask_user("prompt 1"))
        await asyncio.sleep(0.01)
        task2 = asyncio.create_task(ui.ask_user("prompt 2"))
        await asyncio.sleep(0.01)

        ui.submit_user_answer("a1")
        assert await task1 == "a1"

        # Second confirmation now current — the draft is still stashed.
        assert ui._current_confirmation is not None
        assert ui._saved_draft == ("fix the auth bug", 0)
        assert ui._input_field.buffer.text == ""

        ui.submit_user_answer("a2")
        assert await task2 == "a2"

        assert ui._current_confirmation is None
        assert ui._saved_draft is None
        assert ui._input_field.buffer.text == "fix the auth bug"


@pytest.mark.asyncio
async def test_draft_restored_on_cancel():
    """Cancelling pending confirmations hands the draft back."""
    ui = DraftConfirmationUI(draft="fix the auth bug")

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)
        assert ui._input_field.buffer.text == ""

        ui.cancel_pending_confirmations()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert ui._saved_draft is None
        assert ui._input_field.buffer.text == "fix the auth bug"


@pytest.mark.asyncio
async def test_no_input_field_skips_draft_stash():
    """UIs without an input field (e.g. other BaseUI subclasses) are unaffected."""
    ui = MockConfirmationUI()

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)

        ui.submit_user_answer("y")
        assert await task == "y"
        assert ui._current_confirmation is None


@pytest.mark.asyncio
async def test_enter_answer_restores_draft():
    """Regression: the Enter handler's buffer reset must not wipe the draft.

    `_handle_confirmation` clears the buffer BEFORE resolving; the answer text
    is captured first, then resolution restores the stashed draft into the same
    buffer. Previously the reset ran after `_resolve_current`, erasing the draft
    that `_activate_next_confirmation` had just put back.
    """
    ui = DraftConfirmationUI(draft="fix the auth bug")

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)
        assert ui._input_field.buffer.text == ""

        ui._input_field.buffer.text = "y"
        event = MagicMock()
        event.current_buffer = ui._input_field.buffer
        assert ui._handle_confirmation(event) is True

        assert await task == "y"
        assert ui._saved_draft is None
        assert ui._input_field.buffer.text == "fix the auth bug"
        assert ui._input_field.buffer.cursor_position == 0
