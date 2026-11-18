"""Shared default-tool registration for zrb-shipped agents.

`apply_common_tools(host)` gives a ``CommonToolHost`` the shipped tools,
toolset factories and shell-safety policy, so ``LLMChatTask``, ``LLMTask`` and
``SubAgentManager`` share one tool surface. The canonical set lives in
``tool_registry`` (``shared/tool_registry.py``); what it holds and the lazy seed
that supplies it live in ``agent/tool_seed.py``, and this module owns the host
glue that hands them on.

Application only appends per-run providers; nothing resolves until the host's
first agent build, which keeps ``pydantic_ai`` off ``import zrb``. LSP,
worktree, plan-mode and memory tools register conditionally, rare ones use
``defer_loading``.

Not registered here: delegate tools (main-agent-only; sub-agents filter them
via ``zrb_is_delegate_tool``), argument formatters and response handlers
(owned by ``LLMChatTask``, reaching sub-agents through the
``current_tool_confirmation`` ContextVar).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

# Importing the seed is what gives `tool_registry` its built-in content, so a
# host built here resolves the same set an agent hook does.
from zrb.llm.agent import tool_seed  # noqa: F401
from zrb.llm.shared.tool_registry import (  # noqa: F401 -- re-exported
    tool_name,
    tool_registry,
)
from zrb.llm.tool_call.always_approve import (
    register_default_auto_approve,
    register_default_auto_approve_if,
)
from zrb.llm.tool_call.tool_policy.bash_validation import bash_safe_command_policy

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent.types import Tool


@runtime_checkable
class CommonToolHost(Protocol):
    """Minimal interface `apply_common_tools` needs from a host."""

    def append_tool(self, *tool: "Callable | Tool") -> None: ...
    def append_tool_factory(self, *factory: "Callable[[AnyContext], Any]") -> None: ...

    def append_toolset_factory(
        self, *factory: "Callable[[AnyContext], Any]"
    ) -> None: ...


# Tools the harness approves without asking, unless a permission rule says
# otherwise (`register_default_auto_approve`: a user's `ask` or `deny` still
# wins). Each one's blast radius is already bounded, so its prompt was friction
# rather than a decision:
#   - the memory verbs write inside `LLM_MEMORY_DIR` only, through validation a
#     raw `Write` would skip, and commit to that store's own git;
#   - `ReadToolResult` re-reads output the user already approved producing;
#   - `SendMessageTo*` speaks into a sub-agent conversation already opened;
#   - `EnterWorktree` creates an isolated tree; `ExitWorktree`, which deletes
#     one and can drop its branch, is the destructive half and still asks.
DEFAULT_AUTO_APPROVED_TOOLS = (
    "SearchMemory",
    "Remember",
    "Forget",
    "ReadToolResult",
    "SendMessageToSubagent",
    "SendMessageToParent",
    "EnterWorktree",
)


def _is_rename_dry_run(args: dict[str, object]) -> bool:
    """Whether an `LspRenameSymbol` call only reports what it would change."""
    return args.get("dry_run") is True


def apply_common_tools(host: CommonToolHost) -> None:
    """Give *host* the zrb-shipped tools, factories, and approval policies.

    Storage only (safe at construction, no heavy import); call once per host.
    ``SubAgentManager`` filters the result by each sub-agent's ``tools:`` list.

    The approval defaults registered here live in a process-wide registry the
    cascade reads, so they hold for every runner — including the ones
    (``LLMTask``, ``SubAgentManager``) whose host has no policy list to append
    to. That is why the argument-gated one is registered here too and not as a
    tool policy, which only those hosts would miss.
    """
    host.append_tool_factory(_common_tools_provider)
    host.append_toolset_factory(_common_toolsets_provider)
    register_default_auto_approve(*DEFAULT_AUTO_APPROVED_TOOLS)
    # A rename dry run only reports; the same call without `dry_run` writes.
    register_default_auto_approve_if("LspRenameSymbol", _is_rename_dry_run)
    # Read-only git subcommands auto-approve. Hosts without an approval channel
    # (LLMTask, SubAgentManager) have no prepend_tool_policy.
    add_policy = getattr(host, "prepend_tool_policy", None)
    if callable(add_policy):
        add_policy(bash_safe_command_policy())


def _common_tools_provider(
    ctx: "AnyContext",
) -> "list[Callable | Tool]":
    """Per-run provider: the full common tool surface, re-evaluating env gates each build."""
    tools = list(tool_registry.get_tools())
    for factory in tool_registry.get_tool_factories():
        produced = factory(ctx)
        tools.extend(produced if isinstance(produced, list) else [produced])
    return tools


def _common_toolsets_provider(ctx: "AnyContext") -> list:
    """Per-run provider: the common toolset content (e.g. MCP servers)."""
    produced: list = []
    for factory in tool_registry.get_toolset_factories():
        items = factory(ctx)
        produced.extend(items if isinstance(items, list) else [items])
    return produced
