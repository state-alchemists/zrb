"""`AnyUIMessageSink` is the capability the parent-message path needs, and only that.

A delegated sub-agent reports to the agent that started it through the parent
UI's input side (ADR-0108). The check that decides whether a parent exists is
structural, so a protocol is what lets `subagent/` name the capability instead
of the UI above it; a second member would widen that path for every sender, so
the surface is pinned here.
"""

from zrb.llm.contracts.ui.any_ui_message_sink import AnyUIMessageSink


def test_a_message_sink_declares_one_member():
    members = sorted(name for name in dir(AnyUIMessageSink) if not name.startswith("_"))
    assert members == ["input"]


def test_a_ui_that_declares_an_input_side_is_a_sink():
    from zrb.llm.ui.fallback.std_ui import StdUI

    assert isinstance(StdUI(), AnyUIMessageSink)


def test_an_object_with_no_input_side_is_not_a_sink():
    assert not isinstance(object(), AnyUIMessageSink)
