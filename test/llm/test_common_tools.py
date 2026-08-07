"""Which tools ``apply_common_tools`` registers, and under what config.

``CommonToolHost`` is write-only — it has no read-back accessor — so these
drive the public entry point against a recording host and assert on what
reached that boundary, rather than reaching into a task's private tool lists.
"""

import re

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.common_tools import apply_common_tools
from zrb.llm.prompt.profile import MICRO_TOOLS


class RecordingHost:
    """A ``CommonToolHost`` that keeps everything handed to it."""

    def __init__(self):
        self.tools: list = []
        self.tool_factories: list = []
        self.toolset_factories: list = []
        self.policies: list = []

    def add_tool(self, *tool):
        self.tools.extend(tool)

    def add_tool_factory(self, *factory):
        self.tool_factories.extend(factory)

    def add_toolset_factory(self, *factory):
        self.toolset_factories.extend(factory)

    def add_tool_policy(self, *policy):
        self.policies.extend(policy)

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


# ── Preset tool surface (ADR-0075) ──────────────────────────────────────


def _micro_names(monkeypatch) -> set[str]:
    monkeypatch.setenv("ZRB_LLM_PROFILE", "micro")
    monkeypatch.setenv("ZRB_LLM_JOURNAL_ENABLED", "true")
    host = RecordingHost()
    apply_common_tools(host)
    return host.resolved_tool_names()


def test_micro_registers_exactly_its_nine_tools(monkeypatch):
    """The preset's tool axis is the lever a ~3B model actually needs.

    Journaling is left *enabled* to prove the preset outranks it: the point is
    a hard ceiling on tool count, not a second copy of the feature toggles.
    """
    assert _micro_names(monkeypatch) == MICRO_TOOLS


def test_micro_tool_set_is_closed_under_docstring_cross_reference(monkeypatch):
    """A docstring naming an unregistered tool is a dangle nothing can catch.

    Tool docstrings route between each other ("Not to touch files:
    Read/Write/Edit ... RM/MV to remove and move"). Unlike a prompt section,
    a docstring ships with its schema whatever the config, so it cannot carry a
    `<!--requires:-->` guard. This is why the set is nine tools and not six.
    """
    monkeypatch.setenv("ZRB_LLM_PROFILE", "terse")
    every_host = RecordingHost()
    apply_common_tools(every_host)
    dropped = every_host.resolved_tool_names() - MICRO_TOOLS

    monkeypatch.setenv("ZRB_LLM_PROFILE", "micro")
    micro_host = RecordingHost()
    apply_common_tools(micro_host)

    dangling = {}
    for tool in micro_host.tools:
        fn = getattr(tool, "function", tool)
        doc = fn.__doc__ or ""
        hits = {n for n in dropped if re.search(rf"\b{re.escape(n)}\b", doc)}
        if hits:
            dangling[getattr(fn, "__name__", "?")] = sorted(hits)
    assert dangling == {}


def test_micro_keeps_the_shell_safety_policy(monkeypatch):
    """`micro` keeps `Shell`, so the approval rule that guards it must survive.

    The preset trims the tool surface; it must never trim an enforcement the
    remaining surface depends on.
    """
    monkeypatch.setenv("ZRB_LLM_PROFILE", "micro")
    host = RecordingHost()
    apply_common_tools(host)
    assert len(host.policies) == 1


def test_micro_registers_no_deferred_tools(monkeypatch):
    """`defer_loading` needs provider-side tool search, which local runtimes lack.

    A deferred tool there is unreachable rather than cheap, so the preset must
    drop them outright instead of relying on deferral to hide them.
    """
    monkeypatch.setenv("ZRB_LLM_PROFILE", "micro")
    host = RecordingHost()
    apply_common_tools(host)
    assert [t for t in host.tools if getattr(t, "defer_loading", False)] == []


def test_unconstrained_presets_keep_the_full_surface(monkeypatch):
    """Only `micro` constrains the tool axis; `terse`/`mini` must not regress."""
    monkeypatch.setenv("ZRB_LLM_JOURNAL_ENABLED", "true")
    for profile in ("terse", "mini"):
        monkeypatch.setenv("ZRB_LLM_PROFILE", profile)
        host = RecordingHost()
        apply_common_tools(host)
        names = host.resolved_tool_names()
        assert MICRO_TOOLS < names, profile
        assert {"WebSearch", "TodoWrite", "ActivateSkill"} <= names, profile
