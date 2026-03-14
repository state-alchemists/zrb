import asyncio
from dataclasses import dataclass
from typing import Any, TextIO

from zrb.llm.agent.manager import SubAgentManager
from zrb.llm.agent.manager import sub_agent_manager as default_sub_agent_manager
from zrb.llm.agent.run_agent import current_ui, run_agent
from zrb.llm.agent.std_ui import StdUI
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.tool_call.ui_protocol import UIProtocol
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


async def _run_agent_task(
    agent_name: str,
    task: str,
    additional_context: str,
    sub_agent_manager: SubAgentManager,
    ui: UIProtocol,
    flush_ui: bool = False,
) -> AgentTaskResult:
    """Run a single agent task and return structured result.

    Args:
        agent_name: Name of the sub-agent to run.
        task: Task description for the agent.
        additional_context: Optional additional context.
        sub_agent_manager: Manager to create agents from.
        ui: UI protocol for output.
        flush_ui: If True, flush buffered UI after completion (for BufferedUI).

    Returns:
        AgentTaskResult with agent_name, result (if successful), and error (if failed).
    """
    sub_agent = sub_agent_manager.create_agent(agent_name)
    if not sub_agent:
        return AgentTaskResult(agent_name, None, f"Sub-agent '{agent_name}' not found.")

    full_message = task
    if additional_context:
        full_message = f"{task}\n\nContext:\n{additional_context}"

    try:
        result, _ = await run_agent(
            agent=sub_agent,
            message=full_message,
            message_history=[],
            limiter=llm_limiter,
            ui=ui,
        )

        if flush_ui and hasattr(ui, "flush_to_parent"):
            ui.flush_to_parent()

        return AgentTaskResult(agent_name, result, None)

    except (ValueError, RecursionError):
        # Re-raise critical exceptions - callers should handle these
        raise
    except Exception as e:
        # Return other exceptions as error strings for graceful handling
        return AgentTaskResult(agent_name, None, str(e))


def create_delegate_to_agent_tool(
    sub_agent_manager: SubAgentManager | None = None,
):
    if sub_agent_manager is None:
        sub_agent_manager = default_sub_agent_manager
    # Scan for available agents to populate the docstring
    available_agents = sub_agent_manager.scan()
    agent_docs = []
    for agent in available_agents:
        agent_docs.append(f"- `{agent.name}`: {agent.description}")
    agent_doc_section = (
        "\n".join(agent_docs) if agent_docs else "- No sub-agents found."
    )

    async def delegate_to_agent(
        agent_name: str, task: str, additional_context: str = ""
    ) -> str:
        parent_ui = current_ui.get() or StdUI()
        # Generate unique identifier for this agent instance
        unique_id = get_random_name(separator="-", add_random_digit=True)
        prefix = f"[{agent_name}:{unique_id}] "
        buffered_ui = BufferedUI(parent_ui, prefix=prefix)

        task_result = await _run_agent_task(
            agent_name=agent_name,
            task=task,
            additional_context=additional_context,
            sub_agent_manager=sub_agent_manager,
            ui=buffered_ui,
        )

        # Flush any remaining buffered output
        buffered_ui.flush_to_parent()

        if not task_result.success:
            # Agent not found is a critical error - raise it
            if "not found" in (task_result.error or ""):
                raise ValueError(task_result.error)
            return f"Error executing sub-agent '{agent_name}': {task_result.error}"

        # Return result with unique identifier for traceability
        return f"Sub-agent '{agent_name}' ({unique_id}) completed the task:\n\n{task_result.result}\n"

    delegate_to_agent.zrb_is_delegate_tool = True
    delegate_to_agent.__name__ = "DelegateToAgent"
    delegate_to_agent.__doc__ = (
        "Delegates a task to a subagent for isolated execution.\n\n"
        "USAGE:\n"
        "- Provide complete, self-contained context (subagent has NO access to your conversation history)\n"
        "- User cannot see subagent output—you must report all findings\n"
        "- For parallel tasks, use `DelegateToAgentsParallel` instead\n\n"
        "WHEN TO USE: See Delegation Rules in mandate (Section 5).\n\n"
        f"AVAILABLE AGENTS:\n{agent_doc_section}"
    )
    return delegate_to_agent


def create_parallel_delegate_tool(
    sub_agent_manager: SubAgentManager | None = None,
):
    """Create a tool for delegating tasks to multiple agents in parallel."""
    if sub_agent_manager is None:
        sub_agent_manager = default_sub_agent_manager
    # Scan for available agents to populate the docstring
    available_agents = sub_agent_manager.scan()
    agent_docs = []
    for agent in available_agents:
        agent_docs.append(f"- `{agent.name}`: {agent.description}")
    agent_doc_section = (
        "\n".join(agent_docs) if agent_docs else "- No sub-agents found."
    )

    async def parallel_delegate_to_agents(
        tasks: list[dict[str, str]],
    ) -> str:
        """
        Delegate multiple tasks to sub-agents in parallel.

        Each task should be a dict with:
        - agent_name: Name of the sub-agent
        - task: Task description
        - additional_context: (optional) Additional context

        MANDATES:
        - Each sub-agent is a BLANK SLATE without your history/context.
        - User CANNOT see sub-agent outputs directly. You MUST report all findings.
        - Tool approvals are processed sequentially to prevent UI conflicts.

        Args:
            tasks: List of task dicts, each with agent_name and task (and optional additional_context)

        Returns:
            Combined results from all sub-agents.
        """
        if not tasks:
            return "No tasks provided."

        parent_ui = current_ui.get() or StdUI()
        # Shared lock ensures tool approvals are processed sequentially
        # across all parallel agents to prevent UI conflicts
        ui_lock = asyncio.Lock()

        async def run_single_agent(task_spec: dict[str, str]) -> AgentTaskResult:
            task = task_spec.get("task", "")
            additional_context = task_spec.get("additional_context", "")
            agent_name = task_spec.get("agent_name", "")
            # Generate unique identifier for this agent instance
            unique_id = get_random_name(separator="-", add_random_digit=True)
            prefix = f"[{agent_name}:{unique_id}] "
            # All BufferedUI instances share the same lock for sequential user interaction
            buffered_ui = BufferedUI(parent_ui, prefix=prefix, shared_lock=ui_lock)

            result = await _run_agent_task(
                agent_name=agent_name,
                task=task,
                additional_context=additional_context,
                sub_agent_manager=sub_agent_manager,
                ui=buffered_ui,
                flush_ui=False,  # Don't flush here - flush happens inside ask_user under lock
            )
            # After agent completes, flush any remaining buffered output under the lock
            async with ui_lock:
                buffered_ui.flush_to_parent()
            # Return result with unique_id for identification
            return AgentTaskResult(
                f"{agent_name}:{unique_id}",
                result.result,
                result.error,
            )

        # Run all agents in parallel (they share ui_lock for sequential user interaction)
        results = await asyncio.gather(*[run_single_agent(t) for t in tasks])

        # Format combined results
        combined_results = []
        for r in results:
            if not r.success:
                combined_results.append(f"Sub-agent '{r.agent_name}' failed: {r.error}")
            else:
                indented_result = "\n".join(
                    ["  " + line for line in r.result.splitlines()]
                )
                combined_results.append(
                    f"Sub-agent '{r.agent_name}' completed:\n{indented_result}"
                )

        return "\n\n".join(combined_results)

    parallel_delegate_to_agents.zrb_is_delegate_tool = True
    parallel_delegate_to_agents.__name__ = "DelegateToAgentsParallel"
    parallel_delegate_to_agents.__doc__ = (
        "Delegates multiple tasks to subagents in parallel for throughput.\n\n"
        "USAGE:\n"
        "- Each subagent has NO access to your conversation history—provide complete context\n"
        "- User cannot see subagent outputs—you must report all findings\n"
        "- Tool approvals are processed sequentially (may pause for user input)\n\n"
        "Args:\n"
        "    tasks: List of dicts, each with:\n"
        "        - agent_name: Name of the subagent\n"
        "        - task: Task description\n"
        "        - additional_context: (optional) Additional context\n\n"
        "WHEN TO USE: See Delegation Rules in mandate (Section 5).\n\n"
        f"AVAILABLE AGENTS:\n{agent_doc_section}"
    )
    return parallel_delegate_to_agents
