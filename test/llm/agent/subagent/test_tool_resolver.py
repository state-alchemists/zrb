"""Tests for the standalone tool-name resolver used by sub-agents and hooks."""

from zrb.llm.agent.subagent.tool_resolver import (
    canonical_tool_name,
    resolve_tools_by_name,
    resolved_tool_name,
)


def _tool(name: str, is_delegate: bool = False):
    def fn():
        return None

    fn.__name__ = name
    if is_delegate:
        fn.zrb_is_delegate_tool = True
    return fn


class TestCanonicalToolName:
    def test_maps_bash_alias_case_insensitively(self):
        assert canonical_tool_name("bash") == "Shell"
        assert canonical_tool_name("Bash") == "Shell"

    def test_passthrough_for_unknown_name(self):
        assert canonical_tool_name("Read") == "Read"


class TestResolvedToolName:
    def test_uses_tool_name_attr_when_present(self):
        class FakeTool:
            name = "Custom"

        assert resolved_tool_name(FakeTool()) == "Custom"

    def test_falls_back_to_dunder_name(self):
        assert resolved_tool_name(_tool("Read")) == "Read"


class TestResolveToolsByName:
    def test_resolves_from_static_registry(self):
        read_tool = _tool("Read")
        registry = {"Read": read_tool}
        result = resolve_tools_by_name(["Read"], registry)
        assert result == [read_tool]

    def test_alias_resolves_bash_to_shell(self):
        shell_tool = _tool("Shell")
        registry = {"Shell": shell_tool}
        result = resolve_tools_by_name(["bash"], registry)
        assert result == [shell_tool]

    def test_excludes_delegate_tools_from_registry(self):
        delegate = _tool("DelegateToAgent", is_delegate=True)
        registry = {"DelegateToAgent": delegate}
        assert resolve_tools_by_name(["DelegateToAgent"], registry) == []

    def test_unknown_name_resolves_to_nothing(self):
        assert resolve_tools_by_name(["NoSuchTool"], {}) == []

    def test_falls_back_to_factory_when_not_in_registry(self):
        journal_tool = _tool("LogActivity")

        def factory(ctx):
            return [journal_tool]

        result = resolve_tools_by_name(
            ["LogActivity"], registry={}, factories=[factory], ctx=object()
        )
        assert result == [journal_tool]

    def test_factory_not_consulted_when_name_already_in_registry(self):
        registry_tool = _tool("Read")
        calls: list[bool] = []

        def factory(ctx):
            calls.append(True)
            return []

        result = resolve_tools_by_name(
            ["Read"],
            registry={"Read": registry_tool},
            factories=[factory],
            ctx=object(),
        )
        assert result == [registry_tool]
        assert calls == []

    def test_no_factories_means_unresolved_names_are_dropped(self):
        assert resolve_tools_by_name(["LogActivity"], registry={}) == []

    def test_factory_delegate_tool_excluded(self):
        delegate = _tool("DelegateToAgent", is_delegate=True)

        def factory(ctx):
            return delegate

        result = resolve_tools_by_name(
            ["DelegateToAgent"], registry={}, factories=[factory], ctx=object()
        )
        assert result == []
