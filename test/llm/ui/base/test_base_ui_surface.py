"""Public state-property surface of `BaseUI`: properties round-trip, and
part delegators forward."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.hook.manager import HookManager
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.ui.base.message_queue import QueuedMessage
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.multi_ui import MultiUI


class _SurfaceUI(BaseUI):
    def __init__(self, **kwargs):
        self.outputs = []
        super().__init__(**kwargs)

    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        self.outputs.append(sep.join(str(v) for v in values))

    async def ask_user(self, prompt: str, agent_id: str | None = None) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0

    async def run_async(self) -> str:
        return self.last_output


@pytest.fixture
def surface_ui():
    return _SurfaceUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(hook_manager=None, active_hook_manager=None),
        history_manager=MagicMock(),
    )


def _make_entry(text: str) -> QueuedMessage:
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind="message", run=run)


def test_state_properties_roundtrip(surface_ui):
    surface_ui.small_model = "small"
    assert surface_ui.small_model == "small"
    surface_ui.multimodal_model = "big"
    assert surface_ui.multimodal_model == "big"
    surface_ui.conversation_session_name = "session-x"
    assert surface_ui.conversation_session_name == "session-x"

    surface_ui.running_llm_task = None
    assert surface_ui.running_llm_task is None
    surface_ui.cwd = "/tmp"
    assert surface_ui.cwd == "/tmp"
    surface_ui.git_info = "main"
    assert surface_ui.git_info == "main"
    assert surface_ui.markdown_theme is None
    surface_ui.process_messages_task = None
    assert surface_ui.process_messages_task is None
    surface_ui.trigger_tasks = []
    assert surface_ui.trigger_tasks == []
    surface_ui.system_info_task = None
    assert surface_ui.system_info_task is None

    assert surface_ui.snapshot_manager is None
    assert surface_ui.background_tasks == set()
    assert surface_ui.pending_attachments == []
    surface_ui.plan_mode_active = True
    assert surface_ui.plan_mode_active is True
    surface_ui.plan_mode_active = False
    assert surface_ui.plan_mode_active is False
    surface_ui.last_result_data = "answer"
    assert surface_ui.last_result_data == "answer"
    assert surface_ui.ctx is not None
    assert surface_ui.commands is not None


def test_command_alias_lists_read_from_config(surface_ui):
    assert surface_ui.exit_commands == surface_ui.exit_commands
    assert surface_ui.info_commands
    assert surface_ui.save_commands
    assert surface_ui.load_commands
    assert surface_ui.attach_commands
    assert surface_ui.redirect_output_commands
    assert surface_ui.yolo_toggle_commands
    assert surface_ui.set_model_commands
    assert surface_ui.btw_commands
    assert surface_ui.plan_commands
    assert surface_ui.rewind_commands
    assert surface_ui.copy_commands


def test_classify_input_routes_plain_text_as_message(surface_ui):
    assert surface_ui.classify_input("hello there") == "message"
    assert surface_ui.classify_input("   ") == "message"


@pytest.mark.asyncio
async def test_ask_user_choice_forwards_formatted_spec(surface_ui):
    with patch(
        "zrb.llm.ui.base.ui.format_choice_spec", return_value="FORMATTED"
    ) as fmt:
        answer = await surface_ui.ask_user_choice(MagicMock())
    assert answer == "yes"
    fmt.assert_called_once()


@pytest.mark.asyncio
async def test_schedule_command_runs_dispatch_as_background(surface_ui):
    with patch.object(
        surface_ui, "dispatch_command", new_callable=AsyncMock
    ) as dispatch:
        surface_ui.schedule_command("hello")
        await asyncio.sleep(0.02)
    dispatch.assert_awaited_once_with("hello", guarded=True)


@pytest.mark.asyncio
async def test_dispatch_command_forwards_unhandled_text_to_queue(surface_ui):
    await surface_ui.dispatch_command("hello there")


def test_submit_attachment_forwards_path(surface_ui, tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("payload")
    surface_ui.submit_attachment(str(target))
    assert target.exists()


def test_edit_queued_message_logs_child_redraw_failure(surface_ui):
    class _BombRedrawUI(_SurfaceUI):
        def redraw_echo(self, entry):
            raise RuntimeError("splice failed")

    child = _BombRedrawUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(hook_manager=None, active_hook_manager=None),
        history_manager=MagicMock(),
    )
    parent = MagicMock()
    parent.children = [child]
    surface_ui.multi_ui_parent = parent
    entry = _make_entry("old text")
    surface_ui.effective_message_queue.add(entry)
    assert surface_ui.edit_queued_message(entry, "  new text  ") is True
    assert entry.text == "new text"


def test_delete_queued_message_logs_child_echo_removal_failure():
    """One child that cannot splice its echo must not stop the drop, nor the
    other children — the same best-effort fan-out the redraw uses."""

    class _BombRemoveUI(_SurfaceUI):
        def remove_echo(self, entry):
            raise RuntimeError("splice failed")

    child = _BombRemoveUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(hook_manager=None, active_hook_manager=None),
        history_manager=MagicMock(),
    )
    parent = MultiUI([child])
    entry = _make_entry("old text")
    parent.message_queue.put_nowait(entry)

    child.delete_queued_message(entry)

    assert not parent.message_queue.contains(entry)


@pytest.mark.asyncio
async def test_drain_hook_tasks_lets_a_hook_finish(surface_ui):
    """A Stop hook fired as the chat exits gets to finish before teardown."""
    from zrb.llm.hook.types import HookEvent

    finished = asyncio.Event()

    async def slow_hook(*args, **kwargs):
        await asyncio.sleep(0.05)
        finished.set()

    with patch("zrb.llm.hook.manager.hook_manager.execute_hooks", new=slow_hook):
        surface_ui.execute_hook(HookEvent.STOP, {})
        assert len(surface_ui.hook_tasks) == 1
        await surface_ui.drain_hook_tasks(timeout=5)

    assert finished.is_set()
    assert surface_ui.hook_tasks == set()


@pytest.mark.asyncio
async def test_drain_hook_tasks_cancels_a_hook_past_its_timeout(surface_ui):
    from zrb.llm.hook.types import HookEvent

    cancelled = asyncio.Event()

    async def stuck_hook(*args, **kwargs):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    with patch("zrb.llm.hook.manager.hook_manager.execute_hooks", new=stuck_hook):
        surface_ui.execute_hook(HookEvent.STOP, {})
        await surface_ui.drain_hook_tasks(timeout=0.05)
        await asyncio.sleep(0)

    assert cancelled.is_set()


def test_status_badges_are_set_replaced_and_removed_by_key(surface_ui):
    surface_ui.invalidate_ui = MagicMock()

    surface_ui.set_status_badge("mic", "🎤 listening")
    surface_ui.set_status_badge("camera", "📷 on")
    surface_ui.set_status_badge("mic", "🎙️ hearing you…")
    assert surface_ui.status_badges == ("🎙️ hearing you…", "📷 on")

    surface_ui.set_status_badge("mic", None)
    surface_ui.set_status_badge("gone", None)
    assert surface_ui.status_badges == ("📷 on",)
    assert surface_ui.invalidate_ui.call_count == 5


def test_cancel_current_turn_cancels_the_running_turn_and_fires_stop(surface_ui):
    running = MagicMock()
    running.done.return_value = False
    surface_ui.running_llm_task = running
    surface_ui.conversation_session_name = "s1"

    with (
        patch.object(surface_ui, "cancel_pending_confirmations") as release,
        patch.object(surface_ui, "execute_hook") as execute_hook,
    ):
        surface_ui.cancel_current_turn("barge_in")

    release.assert_called_once()
    running.cancel.assert_called_once()
    [(event, data), _] = execute_hook.call_args
    assert event.value == "Stop"
    assert data == {"reason": "barge_in", "session": "s1"}


@pytest.mark.parametrize("done", [None, True])
def test_cancel_current_turn_with_no_turn_running_only_releases(surface_ui, done):
    running = None
    if done:
        running = MagicMock()
        running.done.return_value = True
    surface_ui.running_llm_task = running

    with (
        patch.object(surface_ui, "cancel_pending_confirmations") as release,
        patch.object(surface_ui, "execute_hook") as execute_hook,
    ):
        surface_ui.cancel_current_turn("escape")

    release.assert_called_once()
    execute_hook.assert_not_called()


def test_cancel_current_turn_fires_stop_on_the_turns_own_hook_manager():
    """An interactive chat's UI holds the inner LLMTask, built with the
    manager the turn runs with: that is where Stop must go, not the
    process-wide manager."""
    turn_manager = HookManager(search_dirs=[])
    turn_manager.execute_hooks = AsyncMock(return_value=[])
    ui = _SurfaceUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=LLMTask(name="inner", hook_manager=turn_manager),
        history_manager=MagicMock(),
    )
    running = MagicMock()
    running.done.return_value = False
    ui.running_llm_task = running

    async def cancel_and_settle():
        ui.cancel_current_turn("barge_in")
        await asyncio.sleep(0)

    asyncio.run(cancel_and_settle())

    [call] = turn_manager.execute_hooks.call_args_list
    assert call.args[0].value == "Stop"
    assert call.args[1]["reason"] == "barge_in"


def test_cancel_current_turn_prefers_a_chat_tasks_active_hook_manager():
    """A UI handed the outer chat task: its per-run manager, not its
    configured one (None when each run builds its own)."""
    active = HookManager(search_dirs=[])
    active.execute_hooks = AsyncMock(return_value=[])
    chat_task = MagicMock(active_hook_manager=active, hook_manager=None)
    ui = _SurfaceUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=chat_task,
        history_manager=MagicMock(),
    )
    running = MagicMock()
    running.done.return_value = False
    ui.running_llm_task = running

    async def cancel_and_settle():
        ui.cancel_current_turn("escape")
        await asyncio.sleep(0)

    asyncio.run(cancel_and_settle())

    assert active.execute_hooks.call_args.args[1]["reason"] == "escape"


def _create_child_ui() -> _SurfaceUI:
    return _SurfaceUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(hook_manager=None, active_hook_manager=None),
        history_manager=MagicMock(),
    )


@pytest.mark.parametrize("done", [None, False, True])
def test_is_turn_running_follows_the_ui_own_turn(surface_ui, done):
    running = None
    if done is not None:
        running = MagicMock()
        running.done.return_value = done
    surface_ui.running_llm_task = running

    assert surface_ui.is_turn_running is (done is False)


@pytest.mark.asyncio
async def test_a_multi_ui_child_cancels_the_turn_its_parent_runs():
    """A child of a MultiUI runs no turn itself: Esc on it must reach the
    turn the parent runs, and fire Stop once."""
    child, sibling = _create_child_ui(), MagicMock()
    multi_ui = MultiUI([child, sibling])
    turn_manager = HookManager(search_dirs=[])
    turn_manager.execute_hooks = AsyncMock(return_value=[])
    multi_ui.set_llm_task(MagicMock(active_hook_manager=turn_manager))
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def run():
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    assert child.is_turn_running is False
    await multi_ui.message_queue.put(
        QueuedMessage(text="hi", attachments=[], kind="message", run=run)
    )
    loop_task = asyncio.create_task(multi_ui.process_messages_loop())
    await asyncio.wait_for(started.wait(), 1)
    assert child.is_turn_running is True

    child.cancel_current_turn("escape")
    await asyncio.wait_for(cancelled.wait(), 1)
    await asyncio.sleep(0)
    loop_task.cancel()

    sibling.cancel_pending_confirmations.assert_called_once()
    [call] = turn_manager.execute_hooks.call_args_list
    assert call.args[0].value == "Stop"
    assert call.args[1]["reason"] == "escape"


def test_a_multi_ui_child_with_no_turn_running_only_releases():
    child, sibling = _create_child_ui(), MagicMock()
    multi_ui = MultiUI([child, sibling])
    turn_manager = HookManager(search_dirs=[])
    turn_manager.execute_hooks = AsyncMock(return_value=[])
    multi_ui.set_llm_task(MagicMock(active_hook_manager=turn_manager))

    with patch.object(child, "cancel_pending_confirmations") as release:
        child.cancel_current_turn("escape")

    release.assert_called_once()
    sibling.cancel_pending_confirmations.assert_called_once()
    turn_manager.execute_hooks.assert_not_called()
