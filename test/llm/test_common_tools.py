"""Which tools ``apply_common_tools`` registers, and under what config.

``CommonToolHost`` is write-only — it has no read-back accessor — so these
drive the public entry point against a recording host and assert on what
reached that boundary, rather than reaching into a task's private tool lists.
"""

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.common_tools import apply_common_tools, tool_name
from zrb.llm.permission import Capability, tool_capability


class RecordingHost:
    """A ``CommonToolHost`` that keeps everything handed to it."""

    def __init__(self):
        self.tools: list = []
        self.tool_factories: list = []
        self.toolset_factories: list = []
        self.policies: list = []

    def append_tool(self, *tool):
        self.tools.extend(tool)

    def append_tool_factory(self, *factory):
        self.tool_factories.extend(factory)

    def append_toolset_factory(self, *factory):
        self.toolset_factories.extend(factory)

    def prepend_tool_policy(self, *policy):
        self.policies.extend(policy)

    def resolved_tools(self) -> list:
        """Every tool registered directly or produced by a factory."""
        ctx = Context(shared_ctx=SharedContext(), task_name="probe", color=0, icon="x")
        resolved = list(self.tools)
        for factory in self.tool_factories:
            produced = factory(ctx)
            resolved.extend(produced if isinstance(produced, list) else [produced])
        return resolved

    def resolved_tool_names(self) -> set[str]:
        """Names of every tool registered directly or via a factory."""
        return {name for name in map(tool_name, self.resolved_tools()) if name}


def _names(monkeypatch, journal_enabled: bool) -> set[str]:
    monkeypatch.setenv(
        "ZRB_LLM_JOURNAL_ENABLED", "true" if journal_enabled else "false"
    )
    host = RecordingHost()
    apply_common_tools(host)
    return host.resolved_tool_names()


JOURNAL_TOOLS = {"SearchJournal", "LogActivity", "WriteJournalNote"}


def test_journal_tools_registered_when_journal_enabled(monkeypatch):
    assert JOURNAL_TOOLS <= _names(monkeypatch, True)


def test_journal_tools_unregistered_when_journal_disabled(monkeypatch):
    """The tools *are* the journal interface — no prompt section describes it.

    So the switch has to reach them: with it off there is nothing left telling
    the model a journal exists, which is the surface the toggle exists to remove.
    """
    names = _names(monkeypatch, False)
    assert not (JOURNAL_TOOLS & names)
    # The switch is scoped to journaling: unrelated tools keep registering.
    assert {"Read", "Write", "Grep"} <= names


def test_shell_safety_policy_ships_with_the_shell_tools(monkeypatch):
    """The git approval rule left the prompt, so its enforcement must travel here.

    Registering the allowlist alongside the tools it guards is what makes the
    deleted `git_mandate` section safe to delete.
    """
    monkeypatch.setenv("ZRB_LLM_JOURNAL_ENABLED", "true")
    host = RecordingHost()
    apply_common_tools(host)
    assert len(host.policies) == 1


def test_hosts_without_an_approval_channel_are_skipped(monkeypatch):
    """A host with no add_tool_policy must not blow up registration."""
    monkeypatch.setenv("ZRB_LLM_JOURNAL_ENABLED", "true")

    class PolicylessHost(RecordingHost):
        add_tool_policy = None

    host = PolicylessHost()
    apply_common_tools(host)
    assert {"Read", "Write", "Grep"} <= host.resolved_tool_names()


def test_search_skill_ships_alongside_activate_skill(monkeypatch):
    """SearchSkill is the on-demand window onto the truncated catalogue, so it
    registers on the same surface as the activator."""
    host = RecordingHost()
    apply_common_tools(host)

    assert "SearchSkill" in host.resolved_tool_names()
    assert "ActivateSkill" in host.resolved_tool_names()


def test_every_registered_tool_carries_a_known_capability(monkeypatch):
    """A tool that reaches `apply_common_tools` without a `tag()` call silently
    resolves to `Capability.UNKNOWN` (denied in plan mode) with no error — see
    `_register_tools`'s docstring. This turns that silence into a test failure
    so a forgotten tag is caught at review time instead of in a user's plan-mode
    session."""
    monkeypatch.setenv("ZRB_LLM_JOURNAL_ENABLED", "true")
    host = RecordingHost()
    apply_common_tools(host)

    untagged = {
        tool_name(t)
        for t in host.resolved_tools()
        if tool_capability(t) is Capability.UNKNOWN
    }
    assert not untagged, f"Tools registered without a capability tag: {untagged}"


def test_every_registered_tool_parameter_carries_a_description(monkeypatch):
    """A tool's docstring only reaches the model per-argument via
    `Annotated[..., Field(description=...)]` on the parameter itself —
    pydantic-ai only binds docstring prose to a parameter's schema when it can
    parse a strict `Args:`-style block, so free-form prose (this codebase's
    norm) silently produces an empty per-parameter description. ADR-0055
    records this as the mechanism behind a model reusing an existing journal
    slug with nothing in the schema it was filling in warning that reuse
    overwrites. This turns a missing description into a review-time failure
    instead of a silent gap.

    Scoped to zrb's own tools (`zrb.llm.tool.*`) — third-party MCP toolsets and
    the LSP-server tools (`zrb.llm.lsp.tools`) aren't ours to annotate.
    """
    from pydantic_ai import Tool as PydanticTool

    monkeypatch.setenv("ZRB_LLM_JOURNAL_ENABLED", "true")
    host = RecordingHost()
    apply_common_tools(host)

    gaps: list[str] = []
    for tool in host.resolved_tools():
        fn = getattr(tool, "function", tool)
        if not getattr(fn, "__module__", "").startswith("zrb.llm.tool."):
            continue
        schema = (
            tool.function_schema.json_schema
            if isinstance(tool, PydanticTool)
            else PydanticTool(fn).function_schema.json_schema
        )
        name = tool_name(tool)
        gaps.extend(
            f"{name}.{param}"
            for param, spec in schema.get("properties", {}).items()
            if not spec.get("description")
        )
    assert not gaps, f"Tool parameters with no schema description: {gaps}"
