"""Public ToolRegistry behavior (ADR-0090/ADR-0091 split)."""

from zrb.context.shared_context import SharedContext
from zrb.llm.tool.registry import ToolRegistry, tool_name, tool_registry


def _read():
    def read_file_(ctx):
        return "read"

    read_file_.__name__ = "Read"
    return read_file_


def _write():
    def write_file_(ctx):
        return "write"

    write_file_.__name__ = "Write"
    return write_file_


def _factory(value):
    def factory(ctx):
        return value

    return factory


class RecordingHost:
    def __init__(self):
        self.tools = []
        self.tool_factories = []
        self.toolset_factories = []

    def append_tool(self, *tool):
        self.tools.extend(tool)

    def append_tool_factory(self, *factory):
        self.tool_factories.extend(factory)

    def append_toolset_factory(self, *factory):
        self.toolset_factories.extend(factory)


def test_empty_by_default():
    registry = ToolRegistry()
    assert registry.get_tools() == []
    assert registry.get_tool_factories() == []
    assert registry.get_toolset_factories() == []


def test_defaults_to_fresh_isolated_registry():
    assert ToolRegistry() is not tool_registry


def test_seed_resolved_lazily_on_first_query():
    calls = []

    def seed():
        calls.append(1)
        return ([_read()], [_factory("f")], [_factory("t")])

    registry = ToolRegistry(default=seed)
    assert calls == []
    assert len(registry.get_tools()) == 1
    assert len(calls) == 1
    registry.get_tools()
    assert len(calls) == 1


def test_set_seed_installs_lazy_default():
    registry = ToolRegistry()
    registry.set_seed(lambda: ([_read()], [], []))
    assert [tool_name(t) for t in registry.get_tools()] == ["Read"]

    materialized = ToolRegistry(default=lambda: ([_read()], [], []))
    materialized.append_tool(_write())
    materialized.set_seed(lambda: ([_write()], [], []))
    assert {tool_name(t) for t in materialized.get_tools()} == {"Read", "Write"}


def test_append_prepend_preserve_order():
    registry = ToolRegistry()
    registry.append_tool(_write())
    registry.prepend_tool(_read())
    assert [tool_name(t) for t in registry.get_tools()] == ["Read", "Write"]


def test_append_freezes_seed_default():
    registry = ToolRegistry(default=lambda: ([_read()], [], []))
    registry.append_tool(_write())
    assert {tool_name(t) for t in registry.get_tools()} == {"Read", "Write"}


def test_set_tools_replaces_wholesale():
    registry = ToolRegistry()
    registry.append_tool(_read())
    registry.set_tools([_write()])
    assert {tool_name(t) for t in registry.get_tools()} == {"Write"}


def test_remove_tool_by_value_and_by_name():
    read, write = _read(), _write()
    registry = ToolRegistry()
    registry.append_tool(read, write)
    registry.remove_tool(read)
    assert [tool_name(t) for t in registry.get_tools()] == ["Write"]

    registry.remove_tool("Write")
    assert registry.get_tools() == []


def test_factory_mutations_keep_domain_separate():
    def f1(ctx):
        return "f1"

    def f2(ctx):
        return "f2"

    registry = ToolRegistry()
    registry.append_tool_factory(f1)
    registry.prepend_tool_factory(f2)
    registry.append_tool(_read())
    assert registry.get_tool_factories() == [f2, f1]
    assert len(registry.get_tools()) == 1

    registry.remove_tool_factory(f1)
    assert registry.get_tool_factories() == [f2]


def test_toolset_mutations():
    def t1(ctx):
        return "t1"

    registry = ToolRegistry()
    registry.append_toolset_factory(t1)
    registry.set_toolset_factories([lambda ctx: "t2"])
    assert registry.get_toolset_factories()[0](SharedContext()) == "t2"
    registry.remove_toolset_factory(registry.get_toolset_factories()[0])
    assert registry.get_toolset_factories() == []


def test_apply_to_feeds_host_from_seed(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_JOURNAL_ENABLED", "false")
    registry = ToolRegistry(
        default=lambda: (
            [_read(), _write()],
            [_factory("factory")],
            [_factory("toolset")],
        )
    )
    host = RecordingHost()
    registry.apply_to(host)
    assert {tool_name(t) for t in host.tools} == {"Read", "Write"}
    assert len(host.tool_factories) == 1
    assert len(host.toolset_factories) == 1


def test_llm_tools_name_allowlist_filters_static_tools(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_TOOLS", "Read")
    registry = ToolRegistry(default=lambda: ([_read(), _write()], [], []))
    assert [tool_name(t) for t in registry.get_tools()] == ["Read"]
    monkeypatch.setenv("ZRB_LLM_TOOLS", "")
    assert {tool_name(t) for t in registry.get_tools()} == {"Read", "Write"}
