"""Tests for capability tagging and resolution."""

from zrb.llm.permission import Capability, tag, tool_capability


def test_untagged_is_unknown():
    def f():
        return "x"

    assert tool_capability(f) == Capability.UNKNOWN


def test_tag_sets_capability():
    def f():
        return "x"

    tag(f, Capability.READ)
    assert tool_capability(f) == Capability.READ


def test_tag_returns_callable():
    def f():
        return "x"

    assert tag(f, Capability.EDIT) is f


def test_delegate_attribute_resolves_to_delegate():
    def f():
        return "x"

    f.zrb_is_delegate_tool = True
    assert tool_capability(f) == Capability.DELEGATE


def test_explicit_tag_beats_delegate_attribute():
    def f():
        return "x"

    f.zrb_is_delegate_tool = True
    tag(f, Capability.META)
    assert tool_capability(f) == Capability.META


def test_reads_underlying_function_tag():
    def f():
        return "x"

    tag(f, Capability.NETWORK)

    class FakeTool:
        function = f

    assert tool_capability(FakeTool()) == Capability.NETWORK
