from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, TextIO

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.agent.run.runtime_state import get_current_ui

# Import directly from the inner module to avoid a circular import: the
# subagent package's __init__ triggers `apply_common_tools`, which loads
# zrb.llm.tool, which loads this module — so the package __init__ is still
# mid-load when delegate.py executes its imports.
from zrb.llm.agent.subagent.manager.manager import (
    SubAgentManager,
)
from zrb.llm.agent.subagent.manager.manager import (
    sub_agent_manager as default_sub_agent_manager,
)
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.tool.ambient_state import get_active_worktree
from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.llm.ui.std_ui import StdUI
from zrb.util.string.name import get_random_name


@dataclass
class AgentTaskResult:
    """Result from running a single agent task."""

    agent_name: str
    result: str | None
    error: str | None

    @property
    def success(self) -> bool:
        return self.error is None or self.error == ""


class BufferedUI(UIProtocol):
    """UI wrapper that buffers all output and forwards asks to parent sequentially."""

    def __init__(
        self,
        wrapped_ui: UIProtocol,
        prefix: str = "",
        shared_lock: asyncio.Lock | None = None,
    ):
        self._wrapped = wrapped_ui
        self._prefix = prefix
        self._buffer: list[str] = []
        # Use provided shared lock (for parallel agents) or create own lock
        self._lock = shared_lock if shared_lock is not None else asyncio.Lock()

    async def ask_user(self, prompt: str) -> str:
        # Lock ensures only one agent interacts with parent UI at a time
        # This prevents interleaved output when multiple parallel agents need approval
        async with self._lock:
            # Flush buffered output so user can see what they're being asked about
            self.flush_to_parent()
            prefixed_prompt = (
                f"{self._prefix}{prompt}"
                if self._prefix and prompt.strip() != ""
                else prompt
            )
            return await self._wrapped.ask_user(prefixed_prompt)

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        # Buffer output
        text = sep.join(str(v) for v in values) + end
        self._buffer.append(text)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        return await self._wrapped.run_interactive_command(cmd, shell)

    def get_buffered_output(self) -> str:
        """Get all buffered output."""
        return "".join(self._buffer)

    def flush_to_parent(self) -> None:
        """Flush buffered output to parent UI."""
        output = self.get_buffered_output()
        if output:
            if self._prefix:
                indented = "\n".join(
                    f"{self._prefix}{line}" if line.strip() != "" else ""
                    for line in output.split("\n")
                )
                self._wrapped.append_to_output(indented)
            else:
                self._wrapped.append_to_output(output)
            self._buffer.clear()

    def clear_buffer(self) -> None:
        """Clear the buffer without flushing."""
        self._buffer.clear()

    @property
    def yolo(self) -> bool | frozenset:
        """Delegate YOLO mode to the wrapped parent UI."""
        if hasattr(self._wrapped, "yolo"):
            return self._wrapped.yolo
        return False

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ) -> None:
        """Immediately stream output to parent UI, bypassing the buffer.

        Use this for high-priority status messages that should be visible
        immediately, such as tool call notifications during subagent execution.
        """
        text = sep.join(str(v) for v in values) + end
        if self._prefix:
            # Add prefix to each non-empty line
            lines = text.split("\n")
            text = "\n".join(
                f"{self._prefix}{line}" if line.strip() else "" for line in lines
            )
        self._wrapped.append_to_output(text, kind=kind)


def _format_envelope(
    deliverable: str,
    non_goals: list[str] | str,
    task: str,
    additional_context: str,
) -> str:
    """Assemble a scope-clamped envelope the sub-agent reads first.

    The DELIVERABLE / NON-GOALS / TASK / CONTEXT / BEFORE RETURNING delimiters
    are intentionally uppercase and structural so a sub-agent cannot miss the
    fence while parsing free-form prose.
    """
    if isinstance(non_goals, list) and non_goals:
        non_goals_block = "\n".join(f"  - {item}" for item in non_goals)
    elif isinstance(non_goals, str) and non_goals.strip():
        non_goals_block = f"  - {non_goals.strip()}"
    else:
        non_goals_block = "  - (none declared)"
    context_block = additional_context.strip() if additional_context else "(none)"
    active_wt = get_active_worktree()
    if active_wt:
        wt_line = f"Active worktree: {active_wt}"
        context_block = (
            f"{context_block}\n{wt_line}" if context_block != "(none)" else wt_line
        )
    return (
        f"DELIVERABLE: {deliverable}\n"
        f"NON-GOALS (do NOT do these, even if obviously related):\n"
        f"{non_goals_block}\n\n"
        f"TASK: {task}\n\n"
        f"CONTEXT:\n{context_block}\n\n"
        "BEFORE RETURNING: confirm the deliverable exists exactly as stated "
        "and no non-goal was violated. If the work expanded beyond the "
        "deliverable, stop and report what you skipped rather than including it."
    )


async def _run_agent_task(
    agent_name: str,
    deliverable: str,
    non_goals: list[str],
    task: str,
    additional_context: str,
    sub_agent_manager: SubAgentManager,
    ui: UIProtocol,
    flush_ui: bool = False,
    yolo: bool | None = None,
) -> AgentTaskResult:
    """Run a single agent task and return structured result.

    Args:
        yolo: Override yolo for the sub-agent. None = inherit from parent.
    """
    sub_agent = sub_agent_manager.create_agent(agent_name, yolo=yolo)
    if not sub_agent:
        return AgentTaskResult(
            agent_name,
            None,
            f"Sub-agent '{agent_name}' not found. "
            "[SYSTEM SUGGESTION]: Use ListZrbTasks to see available sub-agents, "
            "or check agent registration in your zrb config.",
        )

    full_message = _format_envelope(deliverable, non_goals, task, additional_context)

    try:
        result, _ = await run_agent(
            agent=sub_agent,
            message=full_message,
            message_history=[],
            limiter=llm_limiter,
            ui=ui,
            yolo=bool(yolo) if yolo is not None else yolo,
        )

        if flush_ui and hasattr(ui, "flush_to_parent"):
            ui.flush_to_parent()

        return AgentTaskResult(agent_name, result, None)

    except RecursionError:
        return AgentTaskResult(
            agent_name,
            None,
            "Recursion depth exceeded. [SYSTEM SUGGESTION]: The sub-agent is looping — "
            "simplify the task or break it into smaller steps.",
        )
    except Exception as e:  # noqa: BLE001
        return AgentTaskResult(agent_name, None, str(e))


def _delegatable_agents(sub_agent_manager: SubAgentManager) -> list:
    """Agents the current permission policy permits delegating to.

    With no policy in force (the default), every scanned agent is returned —
    byte-identical to the historical behavior. When a policy denies delegation
    to a specific agent, it is omitted from the advertised roster so the model
    isn't offered an option it cannot use.
    """
    # lazy: permission is a leaf module.
    from zrb.llm.permission import DENY, Capability, get_effective_policy

    agents = sub_agent_manager.scan()
    policy = get_effective_policy()
    if policy is None:
        return agents
    return [
        a
        for a in agents
        if policy.decide("DelegateToAgent", Capability.DELEGATE, {"agent_name": a.name})
        != DENY
    ]


async def _run_parallel(
    tasks: list[dict[str, Any]],
    sub_agent_manager: SubAgentManager,
) -> str:
    """Run several sub-agent tasks concurrently and return combined results.

    A single atomic call — useful for models that cannot reliably sequence N
    tool-call rounds. Each task gets its own scope clamp and runs blind to the
    others; a shared lock serializes any approval prompts back to the parent UI.
    """
    required = ("agent_name", "deliverable", "task", "non_goals")
    for idx, spec in enumerate(tasks):
        missing = [k for k in required if k not in spec]
        if missing:
            return (
                f"Error: tasks[{idx}] missing required keys: {missing}. "
                "[SYSTEM SUGGESTION]: every task needs agent_name, "
                "deliverable, task, and non_goals (list; [] allowed)."
            )

    parent_ui = get_current_ui() or StdUI()
    ui_lock = asyncio.Lock()

    async def run_single_agent(task_spec: dict[str, Any]) -> AgentTaskResult:
        agent_name = task_spec.get("agent_name", "")
        deliverable = task_spec.get("deliverable", "")
        task = task_spec.get("task", "")
        non_goals = task_spec.get("non_goals", []) or []
        additional_context = task_spec.get("additional_context", "")
        unique_id = get_random_name(separator="-", add_random_digit=True)
        prefix = f"[{agent_name}:{unique_id}] "
        buffered_ui = BufferedUI(parent_ui, prefix=prefix, shared_lock=ui_lock)

        result = await _run_agent_task(
            agent_name=agent_name,
            deliverable=deliverable,
            non_goals=non_goals,
            task=task,
            additional_context=additional_context,
            sub_agent_manager=sub_agent_manager,
            ui=buffered_ui,
            flush_ui=False,
            yolo=None,
        )
        async with ui_lock:
            buffered_ui.flush_to_parent()
        return AgentTaskResult(
            f"{agent_name}:{unique_id}",
            result.result,
            result.error,
        )

    results = await asyncio.gather(*[run_single_agent(t) for t in tasks])

    combined_results = []
    for r in results:
        if not r.success:
            combined_results.append(f"[{r.agent_name}] Error: {r.error}")
        else:
            indented_result = "\n".join(["  " + line for line in r.result.splitlines()])
            combined_results.append(f"[{r.agent_name}] completed:\n{indented_result}")
    return "\n\n".join(combined_results)


def create_delegate_to_agent_tool(
    sub_agent_manager: SubAgentManager | None = None,
):
    if sub_agent_manager is None:
        sub_agent_manager = default_sub_agent_manager
    # Scan for available (and permitted) agents to populate the docstring
    available_agents = _delegatable_agents(sub_agent_manager)
    agent_docs = []
    for agent in available_agents:
        agent_docs.append(f"- `{agent.name}`: {agent.description}")
    agent_doc_section = (
        "\n".join(agent_docs) if agent_docs else "- No sub-agents found."
    )

    async def delegate_to_agent(
        agent_name: str = "",
        deliverable: str = "",
        task: str = "",
        non_goals: list[str] | None = None,
        additional_context: str = "",
        tasks: list[dict[str, Any]] | None = None,
    ) -> str:
        """See module docstring; required-arg signature is the scope clamp."""
        # FAN OUT: a non-empty `tasks` list runs several sub-agents concurrently
        # and returns their results together (one atomic call). Flat args are
        # ignored in that case.
        if tasks:
            return await _run_parallel(tasks, sub_agent_manager)
        if non_goals is None:
            non_goals = []
        missing = [
            name
            for name, value in (
                ("agent_name", agent_name),
                ("deliverable", deliverable),
                ("task", task),
            )
            if not value
        ]
        if missing:
            return (
                f"Error: missing required args: {missing}. "
                "[SYSTEM SUGGESTION]: provide agent_name, deliverable, and task "
                "(non_goals defaults to []), or pass tasks=[...] to fan out."
            )
        parent_ui = get_current_ui() or StdUI()
        # Generate unique identifier for this agent instance
        unique_id = get_random_name(separator="-", add_random_digit=True)
        prefix = f"[{agent_name}:{unique_id}] "
        buffered_ui = BufferedUI(parent_ui, prefix=prefix)

        task_result = await _run_agent_task(
            agent_name=agent_name,
            deliverable=deliverable,
            non_goals=non_goals,
            task=task,
            additional_context=additional_context,
            sub_agent_manager=sub_agent_manager,
            ui=buffered_ui,
        )

        # Flush any remaining buffered output
        buffered_ui.flush_to_parent()

        if not task_result.success:
            return f"Error: {task_result.error}"

        # Return result with unique identifier for traceability
        return f"[{agent_name}:{unique_id}] completed:\n\n{task_result.result}"

    delegate_to_agent.zrb_is_delegate_tool = True
    delegate_to_agent.__name__ = "DelegateToAgent"
    delegate_to_agent.__doc__ = (
        "Delegates a task to a named subagent for isolated execution.\n\n"
        "REQUIRED ARGS:\n"
        "- agent_name: which sub-agent to run.\n"
        "- deliverable: one sentence stating what must exist when the sub-agent "
        "returns. Be concrete — name the artifact (file, function, decision).\n"
        "- task: how to produce the deliverable. Reference exact files, "
        "line numbers, or commands when known.\n"
        "- non_goals: list of adjacent things the sub-agent must NOT do "
        "(e.g. 'do not modify other files', 'do not refactor', 'do not add tests'). "
        "Pass [] only when you are certain no scope expansion risk exists.\n"
        "- additional_context: any extra context the sub-agent needs.\n\n"
        "FAN OUT: to run several independent sub-tasks concurrently in one call, "
        "pass `tasks` as a list of dicts (each with its own agent_name, "
        "deliverable, task, non_goals; additional_context optional) and omit the "
        "flat args. Each task gets its own scope clamp and runs blind to the "
        "others. Prefer this over N separate DelegateToAgentBackground calls.\n\n"
        f"AVAILABLE AGENTS:\n{agent_doc_section}"
    )
    # lazy: permission is a leaf module.
    from zrb.llm.permission import Capability, tag

    tag(delegate_to_agent, Capability.DELEGATE)
    return delegate_to_agent
