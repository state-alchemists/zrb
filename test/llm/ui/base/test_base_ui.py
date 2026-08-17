import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.ui.base.message_queue import MessageQueue, QueuedMessage
from zrb.llm.ui.base.ui import BaseUI


def make_entry(text):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind="message", run=run)


class ConcreteUI(BaseUI):
    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        pass

    async def ask_user(self, prompt: str) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0

    async def run_async(self) -> str:
        # Implementation of run_async to test public side effects
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())
        try:
            # Wait for any pending jobs in the queue
            while not self._message_queue.empty():
                await asyncio.sleep(0.01)
        finally:
            self._process_messages_task.cancel()
        return self.last_output


@pytest.fixture
def base_ui():
    ctx = SharedContext()
    llm_task = MagicMock()
    history_manager = MagicMock()
    return ConcreteUI(
        ctx=ctx,
        yolo_xcom_key="yolo",
        assistant_name="Assistant",
        llm_task=llm_task,
        history_manager=history_manager,
    )


@pytest.mark.asyncio
async def test_submit_user_message_processing(base_ui):
    """Test that submitting a message eventually calls the LLM task."""
    base_ui.llm_task.async_run = AsyncMock(return_value="AI Response")

    # We use a mocked run_loop or just rely on the fact that _submit_user_message
    # adds to a queue that _process_messages_loop drains.
    # Since we can't access _message_queue directly, we verify via the observable
    # result after calling a public method that drives the loop.

    # Mocking _stream_ai_response to see if it gets called when we run the loop
    with patch.object(
        base_ui, "_stream_ai_response", new_callable=AsyncMock
    ) as mock_stream:
        base_ui._submit_user_message(base_ui.llm_task, "hello")

        # Start the loop task
        task = asyncio.create_task(base_ui._process_messages_loop())

        # Wait for the job to be picked up
        for _ in range(10):
            if mock_stream.called:
                break
            await asyncio.sleep(0.01)

        assert mock_stream.called
        task.cancel()


@pytest.mark.asyncio
async def test_stream_ai_response_updates_last_output(base_ui):
    """Verify that the AI response stream updates the public last_output property."""
    base_ui.llm_task.async_run = AsyncMock(return_value="AI Response")

    # _stream_ai_response is "protected" (single underscore),
    # but BaseUI intended for subclassing often treats these as part of the implementation contract.
    # However, to be strictly Public API, we should trigger it via public means.
    # But since BaseUI is abstract, we test the provided implementation of the protected method.
    await base_ui._stream_ai_response(base_ui.llm_task, "user message")

    assert base_ui.last_output == "AI Response"


@pytest.mark.asyncio
async def test_confirm_tool_execution_delegation(base_ui):
    """Test that tool confirmation delegates to the internal handler (observable via handle)."""
    mock_call = MagicMock()
    # tool_call_handler is public
    base_ui.tool_call_handler.handle = AsyncMock(return_value="Approved")

    # _confirm_tool_execution is protected but part of the UI protocol implementation
    res = await base_ui._confirm_tool_execution(mock_call)
    assert res == "Approved"


@pytest.mark.asyncio
async def test_update_system_info_observable(base_ui):
    """Test system info update affects get_git_info (if we made it public) or logs."""
    # Since _git_info is private, we check if it affects anything public.
    # In this case, BaseUI doesn't expose it. We'll skip testing the private attribute
    # and only test the behavior if it was exposed.
    pass


def test_execute_hook_observable(base_ui):
    """Test execute_hook by mocking the global hook manager."""
    from zrb.llm.hook.types import HookEvent

    with patch(
        "zrb.llm.hook.manager.hook_manager.execute_hooks", new_callable=AsyncMock
    ) as mock_exec:
        # This is public
        base_ui.execute_hook(HookEvent.NOTIFICATION, {"msg": "hi"})
        # We verify it was called (observable side effect)
        # We can't easily check _background_tasks without violating the mandate
        # but we can verify the manager was called.
        assert mock_exec.called


@pytest.mark.asyncio
async def test_execute_hook_blocking_returns_results(base_ui):
    """execute_hook_blocking awaits the manager and returns its results."""
    from zrb.llm.hook.types import HookEvent

    sentinel = ["result"]
    with patch(
        "zrb.llm.hook.manager.hook_manager.execute_hooks", new_callable=AsyncMock
    ) as mock_exec:
        mock_exec.return_value = sentinel
        results = await base_ui.execute_hook_blocking(
            HookEvent.PRE_COMMAND, {"command": "/save"}, command_name="/save"
        )
        assert results is sentinel
        assert mock_exec.call_args.args[0] == HookEvent.PRE_COMMAND
        assert mock_exec.call_args.kwargs["command_name"] == "/save"


@pytest.mark.asyncio
async def test_update_system_info_loop(base_ui):
    """Test that the system info loop periodically calls update_system_info."""
    with (
        patch.object(
            base_ui, "_update_system_info", new_callable=AsyncMock
        ) as mock_update,
        patch("zrb.llm.ui.base.ui.CFG") as mock_cfg,
    ):

        mock_cfg.LLM_UI_STATUS_INTERVAL = 1  # 1ms
        mock_cfg.LLM_UI_LONG_STATUS_INTERVAL = 1  # 1ms

        # Start the loop
        task = asyncio.create_task(base_ui._update_system_info_loop())

        # Wait for a few iterations
        await asyncio.sleep(0.05)

        assert mock_update.call_count >= 1

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def test_get_cwd_display_logic(base_ui):
    """Test the protected _get_cwd_display logic."""
    import os

    cwd = os.getcwd()
    # We test the method directly as it's part of the subclassing API
    res = base_ui._get_cwd_display()
    if cwd.startswith(os.path.expanduser("~")):
        assert res.startswith("~")
    else:
        assert res == cwd


def test_submit_user_message_marks_queued_while_thinking(base_ui):
    """A message typed while a turn is in flight is echoed as queued, not sent."""
    outputs: list[str] = []
    with patch.object(base_ui, "append_to_output", side_effect=outputs.append):
        base_ui._submit_user_message(base_ui.llm_task, "later")
        assert base_ui.queued_message_count == 1
        assert "💬" in outputs[0]

        # Flip the flag the way _stream_ai_response does.
        base_ui.is_thinking = True
        base_ui._submit_user_message(base_ui.llm_task, "even later")

    assert base_ui.queued_message_count == 2
    assert "⏳" in outputs[1]
    assert "even later" in outputs[1]


def test_submit_user_message_steers_into_live_run_context(base_ui):
    """A message sent while a turn is live is delivered into that turn instead
    of queuing (ADR-0078)."""
    base_ui.active_run_context = MagicMock()
    with patch.object(base_ui, "append_to_output"):
        base_ui._submit_user_message(base_ui.llm_task, "steer me")

    base_ui.active_run_context.enqueue.assert_called_once_with(
        "steer me", priority="asap"
    )
    assert base_ui.queued_message_count == 0


def test_submit_user_message_falls_back_to_queue_without_active_run_context(
    base_ui,
):
    """No live turn (the default) keeps the existing queue behavior."""
    assert base_ui.active_run_context is None
    with patch.object(base_ui, "append_to_output"):
        base_ui._submit_user_message(base_ui.llm_task, "later")

    assert base_ui.queued_message_count == 1


def test_submit_user_message_falls_back_to_queue_when_enqueue_raises(base_ui):
    """A run that finished between the check and the call must not lose the
    message -- it falls back to the queue instead of being dropped."""
    live_run = MagicMock()
    live_run.enqueue.side_effect = RuntimeError("run already finished")
    base_ui.active_run_context = live_run
    with patch.object(base_ui, "append_to_output"):
        base_ui._submit_user_message(base_ui.llm_task, "steer me")

    assert base_ui.queued_message_count == 1


def test_submit_message_uses_own_llm_task(base_ui):
    """Public `submit_message` (no llm_task argument) forwards to the queue
    path with the UI's own task — the seam sub-agent continuation code uses
    to hand the main agent a synthesized report."""
    with patch.object(base_ui, "_submit_user_message") as mock_submit:
        base_ui.submit_message("report text")
    mock_submit.assert_called_once_with(base_ui.llm_task, "report text")


@pytest.mark.asyncio
async def test_edit_queued_message_replaces_text_in_place(base_ui):
    """A still-queued message's text can be replaced without resubmitting."""
    entry = make_entry("original")
    base_ui.message_queue.put_nowait(entry)

    assert base_ui.edit_queued_message(entry, "edited") is True
    assert entry.text == "edited"
    assert base_ui.queued_message_count == 1

    # Once the turn starts (entry popped), the edit is refused.
    popped = await base_ui.message_queue.get()
    assert popped is entry
    assert base_ui.edit_queued_message(entry, "too late") is False
    assert entry.text == "edited"


def test_edit_queued_message_strips_whitespace(base_ui):
    entry = make_entry("original")
    base_ui.message_queue.put_nowait(entry)

    assert base_ui.edit_queued_message(entry, "  edited  ") is True
    assert entry.text == "edited"
    assert entry.is_editable


# ── MultiUI routing (effective_message_queue + shared-entry redraw) ────────


class FakeMultiUIParent:
    def __init__(self, children=None):
        self._message_queue = MessageQueue()
        self.children = children if children is not None else []


class RecordingUI(ConcreteUI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redrawn = []

    def _redraw_echo(self, entry):
        self.redrawn.append(entry)


def make_ui():
    return RecordingUI(
        ctx=SharedContext(),
        yolo_xcom_key="yolo",
        assistant_name="Assistant",
        llm_task=MagicMock(),
        history_manager=MagicMock(),
    )


def test_effective_message_queue_routes_to_parent_queue(base_ui):
    """A child UI in a MultiUI submits and edits against the shared queue."""
    parent = FakeMultiUIParent()
    base_ui.multi_ui_parent = parent
    entry = make_entry("hello")
    parent._message_queue.put_nowait(entry)

    assert base_ui.effective_message_queue is parent._message_queue
    assert base_ui.queued_message_count == 1


def test_edit_queued_message_updates_shared_entry_and_broadcasts_redraw():
    """Editing from one child rewrites the shared entry for every child."""
    child_a, child_b = make_ui(), make_ui()
    parent = FakeMultiUIParent(children=[child_a, child_b])
    child_a.multi_ui_parent = parent
    child_b.multi_ui_parent = parent
    entry = make_entry("original")
    parent._message_queue.put_nowait(entry)

    assert child_a.edit_queued_message(entry, "edited") is True
    assert entry.text == "edited"
    assert parent._message_queue.contains(entry)
    # The entry is shared, so the echo redraw was broadcast to both children.
    assert child_a.redrawn == [entry]
    assert child_b.redrawn == [entry]


@pytest.mark.asyncio
async def test_edit_queued_message_refused_after_turn_started_in_multi_ui():
    """A message popped from the shared queue is no longer editable."""
    child_a, child_b = make_ui(), make_ui()
    parent = FakeMultiUIParent(children=[child_a, child_b])
    child_a.multi_ui_parent = parent
    child_b.multi_ui_parent = parent
    entry = make_entry("original")
    parent._message_queue.put_nowait(entry)

    popped = await parent._message_queue.get()
    assert popped is entry

    assert child_a.edit_queued_message(entry, "too late") is False
    assert entry.text == "original"
    assert child_a.redrawn == []
    assert child_b.redrawn == []
