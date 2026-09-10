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
