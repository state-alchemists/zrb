"""MultiUI against a child that never implemented an optional hook.

The hooks are declared on `AnyUI` with defaults, so MultiUI calls them on every
child directly. A child that implements none of them must see exactly what the
old probe-and-skip dispatch gave it.
"""

from unittest.mock import MagicMock

import pytest

from zrb.llm.any_ui import AnyUI
from zrb.llm.input_source import BACKGROUND_INPUT, KEYBOARD_INPUT
from zrb.llm.ui.multi_ui import MultiUI
from zrb.llm.ui_fallback.state_defaults import UIStateDefaultsMixin


class _BareChild(UIStateDefaultsMixin, AnyUI):
    """Implements the behavioral half only; mentions no optional hook."""

    def __init__(self):
        self.written: list[tuple[tuple, dict]] = []

    async def ask_user(self, prompt, output_to_parent="", agent_id=None) -> str:
        return ""

    async def ask_user_choice(self, spec, agent_id=None) -> str:
        return ""

    def append_to_output(self, *values, **kwargs):
        self.written.append((values, kwargs))

    def stream_to_parent(self, *values, **kwargs):
        pass

    async def run_interactive_command(self, cmd, shell=False):
        return None

    async def run_async(self):
        return None


class _RecordingChild(_BareChild):
    """Implements the optional hooks MultiUI calls, recording each call."""

    def __init__(self):
        super().__init__()
        self.calls: list[tuple] = []

    def accumulate_usage(self, usage, context_usage=None):
        self.calls.append(("accumulate_usage", usage, context_usage))

    def reset_context_usage(self):
        self.calls.append(("reset_context_usage",))

    def record_tool_call_block(self, collapsed, full):
        self.calls.append(("record_tool_call_block", collapsed, full))

    def record_submitted_message(self, text):
        self.calls.append(("record_submitted_message", text))

    def redraw_echoes(self, entries):
        self.calls.append(("redraw_echoes", tuple(entries)))

    async def update_system_info(self):
        self.calls.append(("update_system_info",))


def test_a_bare_child_takes_every_forwarded_hook_without_output():
    child = _BareChild()
    multi = MultiUI([child])

    multi.accumulate_usage(MagicMock(), None)
    multi.reset_context_usage()
    multi.mark_thinking_block_start()
    multi.collapse_thinking_block("short", "long")
    multi.mark_text_block_start()
    multi.collapse_text_block("short", "long")
    multi.settle_text_block("prose")
    multi.set_stream_indentation("     ")
    multi.start_tool_call("Bash", "call-1")
    multi.end_tool_call("call-1")
    multi.update_tool_prepare("call-1", "preparing")
    multi.update_shell_output("key", "text")
    multi.finish_shell_output("key", "short", "long")

    assert child.written == []


def test_a_bare_child_gets_the_collapsed_tool_call_line():
    child = _BareChild()

    MultiUI([child]).record_tool_call_block("collapsed", "full")

    assert child.written == [(("collapsed",), {"end": "", "kind": "tool_call"})]


def test_a_child_that_records_blocks_does_not_also_get_the_plain_line():
    child = _RecordingChild()

    MultiUI([child]).record_tool_call_block("collapsed", "full")

    assert child.calls == [("record_tool_call_block", "collapsed", "full")]
    assert child.written == []


def test_a_failing_recorder_falls_back_to_the_plain_line():
    class _Broken(_BareChild):
        def record_tool_call_block(self, collapsed, full):
            raise RuntimeError("dead channel")

    child = _Broken()

    MultiUI([child]).record_tool_call_block("collapsed", "full")

    assert child.written == [(("collapsed",), {"end": "", "kind": "tool_call"})]


def test_usage_reaches_a_child_that_meters_it():
    meter, bare = _RecordingChild(), _BareChild()
    usage = MagicMock()

    multi = MultiUI([meter, bare])
    multi.accumulate_usage(usage, None)
    multi.reset_context_usage()

    assert meter.calls == [
        ("accumulate_usage", usage, None),
        ("reset_context_usage",),
    ]


def test_the_primary_child_records_a_typed_message_but_not_a_background_one():
    primary = _RecordingChild()
    multi = MultiUI([primary, _BareChild()])

    multi.submit_user_message(MagicMock(), "typed", KEYBOARD_INPUT)
    multi.submit_user_message(MagicMock(), "notice", BACKGROUND_INPUT)

    assert primary.calls == [("record_submitted_message", "typed")]


def test_a_bare_primary_child_records_nothing_and_does_not_fail():
    multi = MultiUI([_BareChild()])

    multi.submit_user_message(MagicMock(), "typed", KEYBOARD_INPUT)


@pytest.mark.asyncio
async def test_system_info_is_refreshed_on_every_child_after_a_turn():
    refreshing, bare = _RecordingChild(), _BareChild()
    multi = MultiUI([refreshing, bare])
    llm_task = MagicMock()

    async def _answer(*args, **kwargs):
        return "done"

    llm_task.async_run = _answer
    llm_task.tool_confirmation = MagicMock()

    await multi.stream_ai_response(llm_task, "hello", [])

    assert ("update_system_info",) in refreshing.calls


def test_a_delivered_entry_is_redrawn_on_the_primary_child_only_when_it_can():
    primary, bare = _RecordingChild(), _BareChild()
    multi = MultiUI([primary, bare])

    report = multi.send_queued_messages_now(may_interrupt=False, only_ready=True)

    assert report.delivered_entries == ()
    assert primary.calls == [("redraw_echoes", ())]


@pytest.mark.asyncio
async def test_a_confirmation_with_no_winning_ui_and_no_handler_says_so():
    multi = MultiUI([_BareChild()])
    assert multi.last_winning_ui is None

    with pytest.raises(RuntimeError, match="no attached UI and no approval channel"):
        await multi.confirm_tool_execution(MagicMock())
