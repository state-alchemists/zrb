"""Which tools ``apply_common_tools`` registers, and under what config.

``CommonToolHost`` is write-only — it has no read-back accessor — so these
drive the public entry point against a recording host and assert on what
reached that boundary, rather than reaching into a task's private tool lists.

Applying is *storage-only*: the host's tool/toolset lists stay untouched, and
per-run providers are appended through the same public append API a task's own
tools go through. Only running the providers (the host's build-time
resolution) materializes the shipped set — which is what the tests below do,
the way the ``llm_chat`` / ``sub_agent_manager`` singletons' hosts (and any
custom host) resolve at agent build time.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.common_tools import (
    DEFAULT_AUTO_APPROVED_TOOLS,
    apply_common_tools,
    tool_name,
)
from zrb.llm.permission import Capability, tool_capability


@pytest.fixture(autouse=True)
def _memory_on(monkeypatch):
    """Memory on unless a test turns it off.

    It is the only store now, so a test that wants to see the shipped surface
    has to have it on: with it off the three memory tools are simply absent.
    """
    monkeypatch.setenv("ZRB_LLM_MEMORY_ENABLED", "true")


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


MEMORY_TOOLS = {"SearchMemory", "Remember", "Forget"}


def _resolved_names() -> set[str]:
    host = RecordingHost()
    apply_common_tools(host)
    return host.resolved_tool_names()


def test_memory_tools_registered_when_memory_enabled(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MEMORY_ENABLED", "true")
    assert MEMORY_TOOLS <= _resolved_names()


def test_memory_tools_unregistered_when_memory_disabled(monkeypatch):
    """Off is the privacy switch: a session that records nothing offers no verb."""
    monkeypatch.setenv("ZRB_LLM_MEMORY_ENABLED", "false")
    assert not (MEMORY_TOOLS & _resolved_names())


def test_the_rest_of_the_surface_survives_memory_being_off(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MEMORY_ENABLED", "false")
    names = _resolved_names()
    assert not (MEMORY_TOOLS & names)
    assert {"Read", "Write", "Grep"} <= names


def test_memory_tools_are_never_deferred(monkeypatch):
    """A write verb nobody can see is a memory nobody records.

    A `search_tools` step before every recall is the step that gets skipped, so
    all three ship visible.
    """
    monkeypatch.setenv("ZRB_LLM_MEMORY_ENABLED", "true")
    host = RecordingHost()
    apply_common_tools(host)
    by_name = {tool_name(t): t for t in host.resolved_tools()}
    for name in MEMORY_TOOLS:
        # A bare callable is never deferred; a wrapped one says so itself.
        assert getattr(by_name[name], "defer_loading", False) is False


def test_memory_tools_carry_capabilities(monkeypatch):
    """Untagged tools resolve to UNKNOWN, which plan mode denies."""
    monkeypatch.setenv("ZRB_LLM_MEMORY_ENABLED", "true")
    host = RecordingHost()
    apply_common_tools(host)
    by_name = {tool_name(t): t for t in host.resolved_tools()}
    assert tool_capability(by_name["SearchMemory"]) is Capability.READ
    assert tool_capability(by_name["Remember"]) is Capability.EDIT
    assert tool_capability(by_name["Forget"]) is Capability.EDIT


def test_apply_stores_providers_without_resolving_anything(monkeypatch):
    """`apply_common_tools` is storage-only: it appends per-run providers and
    the approval policies, but resolves none of the shipped tools.

    Nothing is handed to the host as a concrete tool at apply time — the
    provider appends are exactly the storage an agent build resolves later —
    which is what keeps the (transitively heavy) resolution off `import zrb`.
    """
    monkeypatch.setenv("ZRB_LLM_MEMORY_ENABLED", "true")
    host = RecordingHost()
    apply_common_tools(host)
    assert host.tools == []
    assert len(host.tool_factories) == 1
    assert len(host.toolset_factories) == 1
    assert len(host.policies) == 1
    # Resolution is the host's build step, not apply's — and it materializes
    # the full shipped set, scoped by config.
    assert {"Read", "Write", "Grep"} <= host.resolved_tool_names()
    assert MEMORY_TOOLS <= host.resolved_tool_names()


def test_read_tool_result_reflects_the_live_spill_flag(monkeypatch):
    """ReadToolResult must not be baked in at registration time: toggling
    LLM_ENABLE_TOOL_SPILL after `apply_common_tools` already ran (e.g. a
    long-lived session whose config changes mid-session) must still be
    reflected the next time tools are resolved for a run."""
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_ENABLE_TOOL_SPILL", False)
    host = RecordingHost()
    apply_common_tools(host)

    assert "ReadToolResult" not in host.resolved_tool_names()

    monkeypatch.setattr(CFG, "LLM_ENABLE_TOOL_SPILL", True)
    assert "ReadToolResult" in host.resolved_tool_names()


def test_shell_safety_policy_ships_with_the_shell_tools(monkeypatch):
    """The git approval rule left the prompt, so its enforcement must travel here.

    Registering the allowlist alongside the tools it guards is what makes the
    deleted `git_mandate` section safe to delete.
    """
    host = RecordingHost()
    apply_common_tools(host)
    assert len(host.policies) == 1


def test_hosts_without_an_approval_channel_are_skipped(monkeypatch):
    """A host with no add_tool_policy must not blow up registration."""

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
    `_seed_default_tools`'s docstring. This turns that silence into a test failure
    so a forgotten tag is caught at review time instead of in a user's plan-mode
    session."""
    host = RecordingHost()
    apply_common_tools(host)

    untagged = {
        tool_name(t)
        for t in host.resolved_tools()
        if tool_capability(t) is Capability.UNKNOWN
    }
    assert not untagged, f"Tools registered without a capability tag: {untagged}"


_SRC = Path(__file__).resolve().parents[2] / "src"

# Imports the tool modules only: never `zrb.llm.common_tools`, so nothing here
# materializes the registry that `apply_common_tools` reads.
_BY_REFERENCE_PROBE = """
import json
from zrb.llm.permission import tool_capability
from zrb.llm.tool.file import read_file, write_file
from zrb.llm.tool.shell import run_shell_command
from zrb.llm.tool.skill import create_activate_skill_tool
from zrb.llm.tool.zrb_task import create_list_zrb_task_tool

print(json.dumps({
    "read": tool_capability(read_file).value,
    "write": tool_capability(write_file).value,
    "shell": tool_capability(run_shell_command).value,
    "skill": tool_capability(create_activate_skill_tool()).value,
    "list_tasks": tool_capability(create_list_zrb_task_tool()).value,
}))
"""


def test_a_tool_handed_on_by_reference_carries_its_own_capability():
    """A tool reaches an agent by reference too: ``LLMTask(tools=[read_file])``.

    That path never resolves this registry, so a tag applied here is invisible
    to it — the tool arrives with whatever tag its own definition carries. When
    the tags lived in the seed instead, every tool on that path resolved to
    `UNKNOWN`, and the sandbox checks an unknown tool's paths as writes: a read
    of anything outside the writable roots was refused. A fresh interpreter
    importing only the tool modules is exactly that path.
    """
    result = subprocess.run(
        [sys.executable, "-c", _BY_REFERENCE_PROBE],
        capture_output=True,
        text=True,
        cwd=_SRC.parent,
        env={**os.environ, "PYTHONPATH": str(_SRC)},
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "read": Capability.READ.value,
        "write": Capability.EDIT.value,
        "shell": Capability.EXECUTE.value,
        "skill": Capability.META.value,
        "list_tasks": Capability.READ.value,
    }


def test_every_registered_tool_parameter_carries_a_description(monkeypatch):
    """A tool's docstring only reaches the model per-argument via
    `Annotated[..., Field(description=...)]` on the parameter itself —
    pydantic-ai only binds docstring prose to a parameter's schema when it can
    parse a strict `Args:`-style block, so free-form prose (this codebase's
    norm) silently produces an empty per-parameter description. ADR-0055
    records this as the mechanism behind a model reusing an existing note slug
    with nothing in the schema it was filling in warning that reuse overwrites.
    This turns a missing description into a review-time failure instead of a
    silent gap.

    Scoped to zrb's own tools (`zrb.llm.tool.*`) — third-party MCP toolsets and
    the LSP-server tools (`zrb.llm.lsp.tools`) aren't ours to annotate.
    """
    from pydantic_ai import Tool as PydanticTool

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


def test_the_approval_defaults_travel_with_the_tool_surface(monkeypatch):
    """A host with no policy list of its own still gets the approval defaults.

    `LLMTask` and `SubAgentManager` have no `prepend_tool_policy`, so a default
    that lived only in a runner's policy list would leave them — and the memory
    reviewer's own agent — asking a question nobody is there to answer. The
    registry is process-wide and the cascade reads it in every runner.
    """
    registered: list[str] = []
    monkeypatch.setattr(
        "zrb.llm.common_tools.register_default_auto_approve",
        lambda *names: registered.extend(names),
    )
    apply_common_tools(RecordingHost())
    assert set(registered) == set(DEFAULT_AUTO_APPROVED_TOOLS)
    assert MEMORY_TOOLS <= set(registered)


def test_the_rename_dry_run_reaches_a_host_with_no_policy_list(monkeypatch):
    """`LspRenameSymbol(dry_run=True)` is bounded by an argument, not by a name.

    A tool policy would have covered it only on hosts with `prepend_tool_policy`
    — `LLMTask` and `SubAgentManager` have none — so the condition is registered
    as a predicate in the same shared registry the other defaults use, and this
    host never implements a policy list at all.
    """

    class PolicylessHost:
        tools: list = []
        tool_factories: list = []
        toolset_factories: list = []

        def append_tool(self, *tool):
            self.tools.extend(tool)

        def append_tool_factory(self, *factory):
            self.tool_factories.extend(factory)

        def append_toolset_factory(self, *factory):
            self.toolset_factories.extend(factory)

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "zrb.llm.common_tools.register_default_auto_approve",
        lambda *names: captured.update({name: None for name in names}),
    )
    monkeypatch.setattr(
        "zrb.llm.common_tools.register_default_auto_approve_if",
        lambda name, predicate: captured.update({name: predicate}),
    )
    apply_common_tools(PolicylessHost())

    rename_predicate = captured["LspRenameSymbol"]
    assert callable(rename_predicate)
    assert rename_predicate({"dry_run": True}) is True
    assert rename_predicate({"new_name": "renamed"}) is False
