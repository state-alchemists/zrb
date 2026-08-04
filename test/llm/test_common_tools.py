"""Which tools ``apply_common_tools`` registers, and under what config.

``CommonToolHost`` is write-only — it has no read-back accessor — so these
drive the public entry point against a recording host and assert on what
reached that boundary, rather than reaching into a task's private tool lists.
"""

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.common_tools import apply_common_tools
from zrb.llm.prompt.tool_guidance import ToolGuidance


class RecordingHost:
    """A ``CommonToolHost`` that keeps everything handed to it."""

    def __init__(self):
        self.tools: list = []
        self.tool_factories: list = []
        self.toolset_factories: list = []
        self.guidance: list[ToolGuidance] = []

    def add_tool(self, *tool):
        self.tools.extend(tool)

    def add_tool_factory(self, *factory):
        self.tool_factories.extend(factory)

    def add_toolset_factory(self, *factory):
        self.toolset_factories.extend(factory)

    def add_tool_guidance(self, *guidance):
        self.guidance.extend(guidance)

    def add_tool_guidance_factory(self, *factory):
        pass

    def add_tool_guidance_section_factory(self, *factory):
        pass

    def resolved_tool_names(self) -> set[str]:
        """Names of every tool registered directly or via a factory."""
        ctx = Context(shared_ctx=SharedContext(), task_name="probe", color=0, icon="x")
        resolved = list(self.tools)
        for factory in self.tool_factories:
            produced = factory(ctx)
            resolved.extend(produced if isinstance(produced, list) else [produced])
        names = set()
        for tool in resolved:
            name = getattr(tool, "__name__", None) or getattr(tool, "name", None)
            if name:
                names.add(str(name))
        return names


def _names(monkeypatch, journal_enabled: bool) -> set[str]:
    monkeypatch.setenv(
        "ZRB_LLM_JOURNAL_ENABLED", "true" if journal_enabled else "false"
    )
    host = RecordingHost()
    apply_common_tools(host)
    return host.resolved_tool_names()


def test_search_journal_registered_when_journal_enabled(monkeypatch):
    assert "SearchJournal" in _names(monkeypatch, True)


def test_search_journal_unregistered_when_journal_disabled(monkeypatch):
    """With the switch off the Journal Protocol section is gone too, so a live
    SearchJournal would be a tool the prompt never mentions."""
    names = _names(monkeypatch, False)
    assert "SearchJournal" not in names
    # The switch is scoped to journaling: unrelated tools keep registering.
    assert {"Read", "Write", "Grep"} <= names
