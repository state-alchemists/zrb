"""Tests for capability tagging and resolution."""

from zrb.llm.permission import Capability, capability_metadata, tag, tool_capability


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


def test_capability_metadata_builds_dict_keyed_by_capability_attr():
    assert capability_metadata(Capability.READ) == {"zrb_capability": Capability.READ}


def test_reads_capability_from_tool_def_metadata():
    """A ``ToolsetTool``-shaped object (no ``.function``, no arbitrary
    attributes — what pydantic-ai's outer per-call dispatch hands the
    permission gate) still resolves its real capability via
    ``tool_def.metadata``, not ``UNKNOWN``."""

    class FakeToolDef:
        metadata = capability_metadata(Capability.EDIT)

    class FakeToolsetTool:
        tool_def = FakeToolDef()

    assert tool_capability(FakeToolsetTool()) == Capability.EDIT


def test_tool_def_metadata_without_capability_key_is_unknown():
    class FakeToolDef:
        metadata = {"unrelated": True}

    class FakeToolsetTool:
        tool_def = FakeToolDef()

    assert tool_capability(FakeToolsetTool()) == Capability.UNKNOWN


def test_tool_def_with_no_metadata_is_unknown():
    class FakeToolDef:
        metadata = None

    class FakeToolsetTool:
        tool_def = FakeToolDef()

    assert tool_capability(FakeToolsetTool()) == Capability.UNKNOWN
