"""`AnyUI`'s side-effect hooks: declared abstract, defaulted by the mixin.

Callers used to ask a UI whether it had a hook before calling it. The hooks are
declared now, so these tests pin that `AnyUI` carries no body for any of them
and that each default in `UIStateDefaultsMixin` is what the absent hook meant.
"""

import pytest

from zrb.llm.any_ui import AnyUI
from zrb.llm.ui_fallback.state_defaults import UIStateDefaultsMixin
from zrb.llm.util.delivery_report import DeliveryOutcome
from zrb.util.cli.markdown import render_markdown

HOOKS = {
    "accumulate_usage",
    "reset_context_usage",
    "append_markdown",
    "append_answer",
    "record_tool_call_block",
    "mark_thinking_block_start",
    "collapse_thinking_block",
    "mark_text_block_start",
    "collapse_text_block",
    "settle_text_block",
    "set_stream_indentation",
    "start_tool_call",
    "end_tool_call",
    "replay_history",
    "update_system_info",
    "record_submitted_message",
    "take_pending_attachments",
    "track_rendered_echo",
    "redraw_echoes",
    "deliver_queued_messages_early",
}


def test_anyui_declares_every_hook_without_a_body():
    assert HOOKS <= AnyUI.__abstractmethods__


def test_the_mixin_implements_every_hook():
    assert HOOKS <= UIStateDefaultsMixin.__dict__.keys()


class _BareUI(UIStateDefaultsMixin, AnyUI):
    """A UI with the behavioral half only; it never mentions an optional hook."""

    def __init__(self):
        self.writes: list[tuple[tuple, dict]] = []

    async def ask_user(self, prompt, output_to_parent="", agent_id=None) -> str:
        return ""

    async def ask_user_choice(self, spec, agent_id=None) -> str:
        return ""

    def append_to_output(self, *values, **kwargs):
        self.writes.append((values, kwargs))

    def stream_to_parent(self, *values, **kwargs):
        pass

    async def run_interactive_command(self, cmd, shell=False):
        return None

    async def run_async(self):
        return None


def test_the_no_op_hooks_do_nothing_and_write_nothing():
    ui = _BareUI()
    assert ui.accumulate_usage(object()) is None
    assert ui.accumulate_usage(object(), None) is None
    assert ui.reset_context_usage() is None
    assert ui.mark_thinking_block_start() is None
    assert ui.collapse_thinking_block("short", "long") is None
    assert ui.mark_text_block_start() is None
    assert ui.collapse_text_block("short", "long") is None
    assert ui.settle_text_block("prose") is None
    assert ui.set_stream_indentation("     ") is None
    assert ui.start_tool_call("Bash", "call-1") is None
    assert ui.end_tool_call("call-1") is None
    assert ui.end_tool_call() is None
    assert ui.record_submitted_message("hello") is None
    assert ui.track_rendered_echo(object(), "header") is None  # type: ignore[arg-type]
    assert ui.redraw_echoes([]) is None
    assert ui.writes == []


@pytest.mark.asyncio
async def test_update_system_info_is_an_awaitable_no_op():
    ui = _BareUI()
    assert await ui.update_system_info() is None
    assert ui.writes == []


def test_a_tool_call_block_is_a_plain_collapsed_tool_call_line():
    ui = _BareUI()
    ui.record_tool_call_block("collapsed", "full form")
    assert ui.writes == [(("collapsed",), {"end": "", "kind": "tool_call"})]


def test_markdown_is_rendered_to_text_without_a_trailing_newline():
    ui = _BareUI()
    ui.append_markdown("**bold** text")
    assert ui.writes == [
        ((render_markdown("**bold** text", width=None),), {"end": ""}),
    ]


def test_an_answer_goes_through_append_markdown():
    class _OverridesMarkdown(_BareUI):
        def append_markdown(self, markdown_text):
            self.writes.append(((markdown_text,), {"via": "append_markdown"}))

    ui = _OverridesMarkdown()
    ui.append_answer("the answer")
    assert ui.writes == [(("the answer",), {"via": "append_markdown"})]


def test_an_answer_is_rendered_like_markdown_when_nothing_is_overridden():
    plain, answered = _BareUI(), _BareUI()
    plain.append_markdown("# Title")
    answered.append_answer("# Title")
    assert answered.writes == plain.writes


def test_a_resumed_history_is_written_as_plain_text():
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    from zrb.llm.util.history_formatter import format_history_as_text

    history = [ModelRequest(parts=[UserPromptPart(content="hi there")])]
    ui = _BareUI()
    ui.replay_history(history)
    assert ui.writes == [((format_history_as_text(history),), {})]


def test_there_are_no_pending_attachments_and_each_call_gets_its_own_list():
    ui = _BareUI()
    first = ui.take_pending_attachments()
    assert first == []
    first.append("x")  # type: ignore[arg-type]
    assert ui.take_pending_attachments() == []


def test_a_ui_without_a_queue_moves_nothing_at_a_checkpoint():
    report = _BareUI().deliver_queued_messages_early()
    assert report.outcome is DeliveryOutcome.NOTHING_MOVED
    assert report.delivered_entries == ()


def test_an_override_replaces_the_default():
    class _Meter(_BareUI):
        def __init__(self):
            super().__init__()
            self.usage: list = []

        def accumulate_usage(self, usage, context_usage=None):
            self.usage.append((usage, context_usage))

    ui = _Meter()
    ui.accumulate_usage("run", "ctx")
    assert ui.usage == [("run", "ctx")]
