"""Public ToolRegistry behavior (ADR-0090)."""

from zrb.context.shared_context import SharedContext
from zrb.llm.contracts.shared.tool_registry import ToolRegistry, tool_name, tool_registry


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


def _named(name):
    def tool_(ctx):
        return name

    tool_.__name__ = name
    return tool_


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


def test_a_read_before_the_seed_arrives_does_not_freeze_it():
    """A read with no seed installed yet is not the last word on the registry.

    An agent hook resolves its tools outside any task run, which can be before
    whatever installs the seed has been imported. That read used to close the
    registry for the rest of the process: the seed was refused afterwards and
    every later caller saw no built-in tools at all.
    """
    registry = ToolRegistry()
    assert registry.get_tools() == []
    assert registry.get_tool_factories() == []
    registry.set_seed(lambda: ([_read()], [_factory("f")], []))
    assert [tool_name(t) for t in registry.get_tools()] == ["Read"]
    assert len(registry.get_tool_factories()) == 1


def test_a_tool_registered_before_the_seed_lands_still_runs_after_it():
    """`append_tool` promises "runs last", so a late seed goes in front.

    Replacing the list instead would drop a tool a `zrb_init.py` registered
    before the built-ins were imported.
    """
    registry = ToolRegistry()
    registry.append_tool(_write())
    registry.set_seed(lambda: ([_read()], [], []))
    assert [tool_name(t) for t in registry.get_tools()] == ["Read", "Write"]


def test_a_tool_prepended_before_the_seed_lands_still_runs_first():
    registry = ToolRegistry()
    registry.prepend_tool(_write())
    registry.set_seed(lambda: ([_read()], [], []))
    assert [tool_name(t) for t in registry.get_tools()] == ["Write", "Read"]


def test_a_tool_removed_before_the_seed_lands_stays_removed():
    """A `zrb_init.py` that drops a built-in runs before the built-ins load.

    Recording the removal and applying it to the seed is the only order that
    honours it: folding the seed in afterwards would put the tool back.
    """
    registry = ToolRegistry()
    registry.remove_tool("Read")
    registry.set_seed(lambda: ([_read(), _write()], [], []))
    assert [tool_name(t) for t in registry.get_tools()] == ["Write"]


def test_a_tool_list_replaced_before_the_seed_lands_is_not_reopened_by_it():
    registry = ToolRegistry()
    registry.set_tools([_write()])
    registry.set_seed(lambda: ([_read()], [], []))
    assert [tool_name(t) for t in registry.get_tools()] == ["Write"]


def test_a_factory_list_replaced_before_the_seed_lands_keeps_its_replacement():
    mine = _factory("mine")
    registry = ToolRegistry()
    registry.set_tool_factories([mine])
    registry.set_seed(lambda: ([_read()], [_factory("seed")], []))
    assert registry.get_tool_factories() == [mine]
    assert [tool_name(t) for t in registry.get_tools()] == ["Read"]


def test_a_factory_prepended_before_the_seed_lands_still_runs_first():
    mine = _factory("mine")
    registry = ToolRegistry()
    registry.prepend_tool_factory(mine)
    registry.set_seed(lambda: ([_read()], [_factory("seed")], []))
    assert [f(None) for f in registry.get_tool_factories()] == ["mine", "seed"]


def test_a_toolset_prepended_before_the_seed_lands_still_runs_first():
    mine = _factory("mine")
    registry = ToolRegistry()
    registry.prepend_toolset_factory(mine)
    registry.set_seed(lambda: ([_read()], [], [_factory("seed")]))
    assert [f(None) for f in registry.get_toolset_factories()] == ["mine", "seed"]


def test_a_removed_prepend_does_not_push_the_seed_behind_an_append():
    """Removing what was prepended must not leave a stale head behind.

    The seed is inserted at the head's offset, so a head that still counts a
    tool the caller removed lands the built-ins after a later append — and
    "append runs last" stops being true.
    """
    first, last = _named("First"), _named("Last")
    registry = ToolRegistry()
    registry.prepend_tool(first)
    registry.remove_tool(first)
    registry.append_tool(last)
    registry.set_seed(lambda: ([_named("Seed")], [], []))
    assert [tool_name(t) for t in registry.get_tools()] == ["Seed", "Last"]


def test_an_append_behind_a_removed_prepend_still_runs_last():
    """The same, in the other order: prepend, append, then drop the prepend.

    The boundary has to shrink by what left it, not by the list's new length —
    the append is still in the list, and the seed belongs in front of it.
    """
    first, last = _named("First"), _named("Last")
    registry = ToolRegistry()
    registry.prepend_tool(first)
    registry.append_tool(last)
    registry.remove_tool(first)
    registry.set_seed(lambda: ([_named("Seed")], [], []))
    assert [tool_name(t) for t in registry.get_tools()] == ["Seed", "Last"]


def test_a_removed_prepend_does_not_push_the_seed_behind_a_factory_append():
    mine, last = _factory("mine"), _factory("last")
    registry = ToolRegistry()
    registry.prepend_tool_factory(mine)
    registry.remove_tool_factory(mine)
    registry.append_tool_factory(last)
    registry.set_seed(lambda: ([_read()], [_factory("seed")], []))
    assert [f(None) for f in registry.get_tool_factories()] == ["seed", "last"]


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
