from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from zrb.llm.tool_call.ui_protocol import ChoiceSpec

from zrb.llm.agent.activity import HasActivityTracking, agent_activity_registry
from zrb.llm.agent.run.runner import run_agent
from zrb.llm.agent.run.runtime_state import get_current_hook_manager, get_current_ui

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
from zrb.llm.hook.manager import hook_manager as default_hook_manager
from zrb.llm.hook.types import HookEvent
from zrb.llm.tool.ambient_state import get_active_worktree
from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.llm.ui.std_ui import StdUI


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
        # Set by _run_agent_task so buffered output also feeds the activity panel.
        self._agent_id: str | None = None
        # Use provided shared lock (for parallel agents) or create own lock
        self._lock = shared_lock if shared_lock is not None else asyncio.Lock()

    def set_activity_id(self, agent_id: str) -> None:
        """Route this sub-agent's output lines to the activity registry."""
        self._agent_id = agent_id

    def set_label(self, prefix: str) -> None:
        """Set the per-line output prefix (e.g. ``[generalist #1] ``)."""
        self._prefix = prefix

    @property
    def label(self) -> str:
        """The output prefix without surrounding whitespace (e.g. ``[generalist #1]``)."""
        return self._prefix.strip()

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
        if self._agent_id:
            agent_activity_registry.update(self._agent_id, text)

    async def ask_user_choice(self, spec: ChoiceSpec) -> str:
        # Mirrors ask_user: serialize parent interaction and flush first.
        async with self._lock:
            self.flush_to_parent()
            return await self._wrapped.ask_user_choice(spec)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        return await self._wrapped.run_interactive_command(cmd, shell)

    async def run_async(self) -> Any:
        return await self._wrapped.run_async()

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
            return getattr(self._wrapped, "yolo")
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
        if self._agent_id:
            agent_activity_registry.update(self._agent_id, text)
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
            "[SYSTEM SUGGESTION]: Check DelegateToAgent's description for available sub-agents, "
            "or check agent registration in your zrb config.",
        )

    full_message = _format_envelope(deliverable, non_goals, task, additional_context)

    # SubagentStart/Stop fire on the parent run's hook manager (Claude semantics:
    # the parent observes its subagents). agent_type is the delegated agent's name.
    agent_id = uuid.uuid4().hex[:8]
    _tracks_activity = isinstance(ui, HasActivityTracking)
    if _tracks_activity:
        ui.set_activity_id(agent_id)
        ordinal = agent_activity_registry.start(
            agent_id, agent_name, task=deliverable or task
        )
        # Label the output stream with the panel ordinal, unless the caller
        # already set a meaningful prefix (background delegation uses its handle).
        if not ui.label:
            ui.set_label(f"[{agent_name} #{ordinal}] ")
    await _fire_subagent_hook(HookEvent.SUBAGENT_START, agent_name, agent_id)
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
            getattr(ui, "flush_to_parent")()

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
    finally:
        if _tracks_activity:
            agent_activity_registry.finish(agent_id)
        await _fire_subagent_hook(HookEvent.SUBAGENT_STOP, agent_name, agent_id)


async def _fire_subagent_hook(event: HookEvent, agent_name: str, agent_id: str) -> None:
    """Fire SubagentStart/Stop (observe-only) on the parent run's hook manager,
    falling back to the module singleton. Never raises."""
    manager = get_current_hook_manager() or default_hook_manager
    try:
        await manager.execute_hooks(
            event,
            {"agent_type": agent_name, "agent_id": agent_id},
            agent_type=agent_name,
            agent_id=agent_id,
        )
    except Exception:
        pass


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
        # _run_agent_task assigns the [agent_name #ordinal] label.
        buffered_ui = BufferedUI(parent_ui, shared_lock=ui_lock)

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
            buffered_ui.label or f"[{agent_name}]",
            result.result,
            result.error,
        )

    results = await asyncio.gather(*[run_single_agent(t) for t in tasks])

    combined_results = []
    for r in results:
        # r.agent_name already carries its [agent_name #ordinal] label.
        if not r.success:
            combined_results.append(f"{r.agent_name} Error: {r.error}")
        else:
            indented_result = "\n".join(
                ["  " + line for line in (r.result or "").splitlines()]
            )
            combined_results.append(f"{r.agent_name} completed:\n{indented_result}")
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
        # Mutable defaults are intentional here: pydantic-ai builds a Pydantic v2
        # model from this signature and internally converts mutable defaults to
        # default_factory, so each tool call gets a fresh list. Using `= []`
        # instead of `list[str] | None = None` keeps the JSON schema compact
        # (avoids anyOf + null union that bloats every tool description sent to the LLM).
        non_goals: list[str] = [],  # noqa: B006
        additional_context: str = "",
        tasks: list[dict[str, Any]] = [],  # noqa: B006
    ) -> str:
        """See module docstring; required-arg signature is the scope clamp."""
        # FAN OUT: a non-empty `tasks` list runs several sub-agents concurrently
        # and returns their results together (one atomic call). Flat args are
        # ignored in that case.
        if tasks:
            return await _run_parallel(tasks, sub_agent_manager)
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
        # _run_agent_task assigns the [agent_name #ordinal] label (the panel
        # is the legend); no opaque per-instance id is shown to the user.
        buffered_ui = BufferedUI(parent_ui)

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

        label = buffered_ui.label or f"[{agent_name}]"
        return f"{label} completed:\n\n{task_result.result}"

    delegate_to_agent.zrb_is_delegate_tool = True  # type: ignore[attr-defined]
    delegate_to_agent.__name__ = "DelegateToAgent"
    delegate_to_agent.__doc__ = (
        "Delegates a task to a named subagent for isolated execution.\n\n"
        "- deliverable: concrete artifact that must exist on return (name the file, function, or decision).\n"
        "- task: how to produce it — reference exact files, line numbers, or commands when known.\n"
        "- non_goals: things the sub-agent must NOT do (scope clamp). Pass [] only when certain.\n\n"
        "FAN OUT: pass tasks=[{agent_name, deliverable, task, non_goals, ...}, ...] to run multiple "
        "sub-agents concurrently in one call. Flat args are ignored when tasks is non-empty.\n\n"
        f"AVAILABLE AGENTS:\n{agent_doc_section}"
    )
    # lazy: permission is a leaf module.
    from zrb.llm.permission import Capability, tag

    tag(delegate_to_agent, Capability.DELEGATE)
    return delegate_to_agent
