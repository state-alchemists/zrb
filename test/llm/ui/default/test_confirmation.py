import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.ui.default.confirmation import UIConfirmation


class _ForwardsToConfirmation:
    """Shared `__getattr__` shim: forwards to the composed `UIConfirmation`.

    Every test double here used to subclass `UIConfirmation` directly; under
    composition each instead builds `self._confirmation = UIConfirmation(self)`
    and forwards unresolved attribute lookups (public API, plus the private
    methods these tests call directly) to it.
    """

    def __getattr__(self, name):
        confirmation = self.__dict__.get("_confirmation")
        if confirmation is None:
            raise AttributeError(name)
        return getattr(confirmation, name)

    def resolve_current(self, text, echo):
        return self._confirmation.resolve_current(text, echo)

    def begin_choice(self, spec):
        pass

    def end_choice(self):
        pass


class MockConfirmationUI(_ForwardsToConfirmation):
    def __init__(self):
        self.confirmation_queue = []
        self.confirmation_output_buffer = []
        self.current_confirmation = None
        self._confirmation = UIConfirmation(self)

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


class DraftConfirmationUI(_ForwardsToConfirmation):
    """Wires a fake input field so the draft stash/restore paths run."""

    def __init__(self, draft=""):
        self.confirmation_queue = []
        self.confirmation_output_buffer = []
        self.current_confirmation = None
        self.input_field = FakeInputField(draft)
        self._confirmation = UIConfirmation(self)
        # Public alias so tests can reach the composed part without a
        # leading-underscore dotted expression (counted by the
        # private-test-access ratchet).
        self.confirmation_part = self._confirmation

    def append_to_output(self, text, end="\n"):
        pass

    def invalidate_ui(self):
        pass


class ViewAwareConfirmationUI(_ForwardsToConfirmation):
    """Adds the `viewing_agent_id`/`conversation_session_name` state
    `_resolve_for_agent`/`handle_confirmation` read (normally supplied by
    `UIAgentPicker` in the composed default `UI`)."""

    def __init__(self, viewing_agent_id=None):
        self.confirmation_queue = []
        self.confirmation_output_buffer = []
        self.current_confirmation = None
        self.viewing_agent_id = viewing_agent_id
        self.conversation_session_name = "sess"
        self._confirmation = UIConfirmation(self)

    def append_to_output(self, text, end="\n"):
        pass

    def invalidate_ui(self):
        pass

    def has_current_confirmation(self):
        return self.current_confirmation is not None

    def confirmation_count(self):
        return len(self.confirmation_queue)

    def handle_confirmation(self, event):
        return self._confirmation.handle_confirmation(event)


class GuardedConfirmationUI(_ForwardsToConfirmation):
    """Replicates `UIOutput.append_to_output`'s buffer guard.

    Output appended while a confirmation is pending AND the agent is thinking is
    buffered (to stop main-agent tokens interleaving with a prompt). This is the
    exact condition that previously swallowed the confirmation prompt itself.
    """

    def __init__(self, is_thinking=True):
        self.confirmation_queue = []
        self.confirmation_output_buffer = []
        self.current_confirmation = None
        self._is_thinking = is_thinking
        self.rendered = []
        self._confirmation = UIConfirmation(self)

    def append_to_output(self, *values, end="\n", **kwargs):
        content = " ".join(str(v) for v in values) + end
        if self.current_confirmation is not None and self._is_thinking:
            self.confirmation_output_buffer.append(content)
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
        assert ui.current_confirmation is not None

        # Second call is queued
        task2 = asyncio.create_task(ui.ask_user("prompt 2"))
        await asyncio.sleep(0.01)
        assert len(ui.confirmation_queue) == 2  # task1 and task2

        # Submit first answer
        ui.submit_user_answer("answer 1")
        res1 = await task1
        assert res1 == "answer 1"

        # Second call should now be current
        assert ui.current_confirmation is not None

        # Submit second answer
        ui.submit_user_answer("answer 2")
        res2 = await task2
        assert res2 == "answer 2"
        assert ui.current_confirmation is None


@pytest.mark.asyncio
async def test_resolve_current_echo_does_not_double_the_trailing_newline():
    """Regression: `echo` already carries its own trailing "\\n"
    (`submit_user_answer` builds it as `text + "\\n"`); `append_to_output`'s
    default `end="\\n"` used to add a second one, printing a blank line
    after every single confirmation answer."""
    ui = MockConfirmationUI()
    ui.append_to_output = MagicMock()

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt 1"))
        await asyncio.sleep(0.01)
        ui.append_to_output.reset_mock()  # drop the prompt-render call
        ui.submit_user_answer("y")
        assert await task == "y"

    ui.append_to_output.assert_called_once_with("y\n", end="")


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
        assert ui.confirmation_output_buffer == []
        # ...and the confirmation is now correctly marked pending.
        assert ui.current_confirmation is not None

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
        assert ui.confirmation_output_buffer == []

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
        assert ui.confirmation_output_buffer  # held, not rendered
        assert not any("main token" in c for c in ui.rendered)

        # 3. User answers -> buffered main-agent output flushes all at once.
        ui.submit_user_answer("y")
        assert await task == "y"
        assert any("main token 1" in c for c in ui.rendered)
        assert any("main token 2" in c for c in ui.rendered)
        assert ui.confirmation_output_buffer == []


@pytest.mark.asyncio
async def test_cancel_pending_confirmations():
    ui = MockConfirmationUI()

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)

        ui.cancel_pending_confirmations()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert ui.current_confirmation is None
        assert len(ui.confirmation_queue) == 0


@pytest.mark.asyncio
async def test_draft_stashed_and_cleared_when_confirmation_activates():
    """The half-typed message leaves the field while a confirmation is pending."""
    ui = DraftConfirmationUI(draft="fix the auth bug")

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)

        assert ui.current_confirmation is not None
        assert getattr(ui.confirmation_part, "_saved_draft") == ("fix the auth bug", 0)
        assert ui.input_field.buffer.text == ""

        ui.submit_user_answer("y")
        assert await task == "y"


@pytest.mark.asyncio
async def test_draft_restored_with_cursor_after_answer():
    """After the confirmation resolves, text and cursor position come back."""
    ui = DraftConfirmationUI(draft="fix the auth bug")
    ui.input_field.buffer.cursor_position = 5

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)
        assert ui.input_field.buffer.text == ""

        ui.submit_user_answer("n")
        assert await task == "n"

        assert getattr(ui.confirmation_part, "_saved_draft") is None
        assert ui.input_field.buffer.text == "fix the auth bug"
        assert ui.input_field.buffer.cursor_position == 5


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
        assert ui.current_confirmation is not None
        assert getattr(ui.confirmation_part, "_saved_draft") == ("fix the auth bug", 0)
        assert ui.input_field.buffer.text == ""

        ui.submit_user_answer("a2")
        assert await task2 == "a2"

        assert ui.current_confirmation is None
        assert getattr(ui.confirmation_part, "_saved_draft") is None
        assert ui.input_field.buffer.text == "fix the auth bug"


@pytest.mark.asyncio
async def test_draft_restored_on_cancel():
    """Cancelling pending confirmations hands the draft back."""
    ui = DraftConfirmationUI(draft="fix the auth bug")

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)
        assert ui.input_field.buffer.text == ""

        ui.cancel_pending_confirmations()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert getattr(ui.confirmation_part, "_saved_draft") is None
        assert ui.input_field.buffer.text == "fix the auth bug"


@pytest.mark.asyncio
async def test_no_input_field_skips_draft_stash():
    """UIs without an input field (e.g. other BaseUI subclasses) are unaffected."""
    ui = MockConfirmationUI()

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)

        ui.submit_user_answer("y")
        assert await task == "y"
        assert ui.current_confirmation is None


@pytest.mark.asyncio
async def test_enter_answer_restores_draft():
    """Regression: the Enter handler's buffer reset must not wipe the draft.

    `handle_confirmation` clears the buffer BEFORE resolving; the answer text
    is captured first, then resolution restores the stashed draft into the same
    buffer. Previously the reset ran after `resolve_current`, erasing the draft
    that `_activate_next_confirmation` had just put back.
    """
    ui = DraftConfirmationUI(draft="fix the auth bug")

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)
        assert ui.input_field.buffer.text == ""

        ui.input_field.buffer.text = "y"
        event = MagicMock()
        event.current_buffer = ui.input_field.buffer
        assert ui.handle_confirmation(event) is True

        assert await task == "y"
        assert getattr(ui.confirmation_part, "_saved_draft") is None
        assert ui.input_field.buffer.text == "fix the auth bug"
        assert ui.input_field.buffer.cursor_position == 0


@pytest.mark.asyncio
async def test_viewing_agent_resolves_its_own_queued_request_not_fifo_head():
    """Regression: pressing y/n/e while viewing a sub-agent's live view must
    resolve *that* agent's own pending request, even when it's not yet the
    main FIFO's current one (another agent's request arrived first)."""
    ui = ViewAwareConfirmationUI(viewing_agent_id="sub4")
    fake_entry = MagicMock()

    with (
        patch("prompt_toolkit.application.get_app"),
        patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry.get",
            return_value=fake_entry,
        ),
    ):
        task1 = asyncio.create_task(ui.ask_user("sub1 prompt", agent_id="sub1"))
        await asyncio.sleep(0.01)
        task4 = asyncio.create_task(ui.ask_user("sub4 prompt", agent_id="sub4"))
        await asyncio.sleep(0.01)

        # sub1's request became current; sub4's is still queued behind it.
        assert ui.has_current_confirmation()
        assert ui.confirmation_count() == 2

        event = MagicMock()
        event.current_buffer = FakeBuffer("y")
        assert ui.handle_confirmation(event) is True

        # sub4's future resolved, sub1's is untouched and still current.
        assert await task4 == "y"
        assert not task1.done()
        fake_entry.buffered_ui.append_to_output.assert_called_once_with("y\n")

        ui.submit_user_answer("y")
        assert await task1 == "y"


@pytest.mark.asyncio
async def test_viewing_agent_with_own_current_request_echoes_to_its_view():
    """When the viewed agent's request IS the FIFO head, resolving it via the
    view-routed path still echoes the answer into its own buffer, not the
    main transcript."""
    ui = ViewAwareConfirmationUI(viewing_agent_id="sub1")
    fake_entry = MagicMock()

    with (
        patch("prompt_toolkit.application.get_app"),
        patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry.get",
            return_value=fake_entry,
        ),
    ):
        task1 = asyncio.create_task(ui.ask_user("sub1 prompt", agent_id="sub1"))
        await asyncio.sleep(0.01)

        event = MagicMock()
        event.current_buffer = FakeBuffer("y")
        assert ui.handle_confirmation(event) is True

        assert await task1 == "y"
        fake_entry.buffered_ui.append_to_output.assert_called_once_with("y\n")


@pytest.mark.asyncio
async def test_viewing_agent_with_nothing_pending_does_not_steal_others_confirmation():
    """Viewing a sub-agent with no pending request of its own must not
    resolve some other agent's (or the main agent's) confirmation -- it
    falls through so the typed text is dispatched as a chat message instead."""
    ui = ViewAwareConfirmationUI(viewing_agent_id="sub-idle")

    with patch("prompt_toolkit.application.get_app"):
        task1 = asyncio.create_task(ui.ask_user("sub1 prompt", agent_id="sub1"))
        await asyncio.sleep(0.01)

        event = MagicMock()
        event.current_buffer = FakeBuffer("hello")
        assert ui.handle_confirmation(event) is False
        assert ui.has_current_confirmation()  # sub1's untouched

        ui.submit_user_answer("y")
        assert await task1 == "y"


@pytest.mark.asyncio
async def test_not_viewing_any_agent_keeps_fifo_behavior():
    """Regression guard: with no sub-agent view active, resolution is exactly
    the pre-existing FIFO-head behavior."""
    ui = ViewAwareConfirmationUI(viewing_agent_id=None)

    with patch("prompt_toolkit.application.get_app"):
        task1 = asyncio.create_task(ui.ask_user("sub1 prompt", agent_id="sub1"))
        await asyncio.sleep(0.01)
        task4 = asyncio.create_task(ui.ask_user("sub4 prompt", agent_id="sub4"))
        await asyncio.sleep(0.01)

        event = MagicMock()
        event.current_buffer = FakeBuffer("y")
        assert ui.handle_confirmation(event) is True

        # The FIFO head (sub1's request) resolved, not sub4's.
        assert await task1 == "y"
        assert not task4.done()

        ui.submit_user_answer("y")
        assert await task4 == "y"
