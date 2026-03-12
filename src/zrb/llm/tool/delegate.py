import asyncio
import sys
from typing import Any, TextIO

from zrb.llm.agent.manager import (
    SubAgentManager,
)
from zrb.llm.agent.manager import sub_agent_manager as default_sub_agent_manager
from zrb.llm.agent.run_agent import current_ui, run_agent
from zrb.llm.agent.std_ui import StdUI
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.tool_call.ui_protocol import UIProtocol


class IndentedUI(UIProtocol):
    """UI wrapper that indents all output."""

    def __init__(self, wrapped_ui: UIProtocol, indent: str = "  "):
        self._wrapped = wrapped_ui
        self._indent = indent
        self._last_char = "\n"
        self._first_time = True

    async def ask_user(self, prompt: str) -> str:
        indented_prompt = self._indent_text(prompt)
        return await self._wrapped.ask_user(indented_prompt)

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        if self._first_time:
            self._wrapped.append_to_output("\n", end="", file=file, flush=flush)
            self._first_time = False
        text = sep.join(str(v) for v in values) + end
        indented_text = self._indent_text(text)
        self._wrapped.append_to_output(indented_text, end="", file=file, flush=flush)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        return await self._wrapped.run_interactive_command(cmd, shell)

    def _indent_text(self, text: str) -> str:
        if not text:
            return text
        result = []
        for char in text:
            if self._last_char == "\n":
                result.append(self._indent)
            if char == "\r":
                result.append("\r" + self._indent)
                self._last_char = " "
                continue
            if char == "\n":
                result.append("\n")
                self._last_char = "\n"
                continue
            result.append(char)
            self._last_char = char
        return "".join(result)


class BufferedUI(UIProtocol):
    """UI wrapper that buffers all output and forwards asks to parent sequentially."""

    def __init__(self, wrapped_ui: UIProtocol, prefix: str = ""):
        self._wrapped = wrapped_ui
        self._prefix = prefix
        self._buffer: list[str] = []
        self._lock = asyncio.Lock()

    async def ask_user(self, prompt: str) -> str:
        # Forward ask to parent UI (this will block until user responds)
        async with self._lock:
            prefixed_prompt = f"{self._prefix}{prompt}" if self._prefix else prompt
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
                    f"{self._prefix}{line}" for line in output.split("\n")
                )
                self._wrapped.append_to_output(indented)
            else:
                self._wrapped.append_to_output(output)
            self._buffer.clear()

    def clear_buffer(self) -> None:
        """Clear the buffer without flushing."""
        self._buffer.clear()


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
        # 1. Load Agent (YOLO is handled dynamically via current_yolo context)
        sub_agent = sub_agent_manager.create_agent(agent_name)
        if not sub_agent:
            raise ValueError(f"Sub-agent '{agent_name}' not found.")

        # 2. Prepare Message
        full_message = task
        if additional_context:
            full_message = f"{task}\n\nContext:\n{additional_context}"

        # 3. Setup Indented UI
        parent_ui = current_ui.get() or StdUI()
        indented_ui = IndentedUI(parent_ui)

        # 4. Run Agent (YOLO and tool_confirmation are inherited via context variables)
        try:
            # FORCE NEWLINE directly to stderr to guarantee visual separation
            result, _ = await run_agent(
                agent=sub_agent,
                message=full_message,
                message_history=[],  # Isolated history
                limiter=llm_limiter,  # Shared limiter
                ui=indented_ui,
                # yolo and tool_confirmation are inherited from context variables
            )

            # Format the final result with indentation
            indented_result = "\n".join(["  " + line for line in result.splitlines()])
            # Return the result without a leading newline to prevent extra gaps
            return (
                f"Sub-agent '{agent_name}' completed the task:\n\n{indented_result}\n"
            )

        except (ValueError, RecursionError):
            raise
        except Exception as e:
            return f"Error executing sub-agent '{agent_name}': {e}"

    delegate_to_agent.zrb_is_delegate_tool = True
    delegate_to_agent.__name__ = "DelegateToAgent"
    delegate_to_agent.__doc__ = (
        "Delegates a task to a sub-agent. Use primarily for context isolation on massive tasks (e.g., parsing huge logs, deep research) to avoid polluting your primary context window, or when a user explicitly requests a specific custom agent.\n\n"
        "MANDATES:\n"
        "- Sub-agent is a BLANK SLATE without your history/context. Provide ALL self-contained context (paths, rules, code).\n"
        "- User CANNOT see sub-agent output. You MUST extract and report all findings in your final response.\n\n"
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

        async def run_single_agent(task_spec: dict[str, str]) -> tuple[str, str, str]:
            """Run a single agent and return (agent_name, result, error)."""
            agent_name = task_spec.get("agent_name", "")
            task = task_spec.get("task", "")
            additional_context = task_spec.get("additional_context", "")

            try:
                sub_agent = sub_agent_manager.create_agent(agent_name)
                if not sub_agent:
                    return agent_name, "", f"Sub-agent '{agent_name}' not found."

                full_message = task
                if additional_context:
                    full_message = f"{task}\n\nContext:\n{additional_context}"

                # Use buffered UI to collect output
                prefix = f"[{agent_name}] "
                buffered_ui = BufferedUI(parent_ui, prefix=prefix)

                result, _ = await run_agent(
                    agent=sub_agent,
                    message=full_message,
                    message_history=[],
                    limiter=llm_limiter,
                    ui=buffered_ui,
                    # yolo and tool_confirmation are inherited from context variables
                )

                # Flush any remaining buffered output
                buffered_ui.flush_to_parent()

                return agent_name, result, ""

            except Exception as e:
                return agent_name, "", str(e)

        # Run all agents in parallel
        results = await asyncio.gather(*[run_single_agent(t) for t in tasks])

        # Format combined results
        combined_results = []
        for agent_name, result, error in results:
            if error:
                combined_results.append(f"Sub-agent '{agent_name}' failed: {error}")
            else:
                indented_result = "\n".join(["  " + line for line in result.splitlines()])
                combined_results.append(
                    f"Sub-agent '{agent_name}' completed:\n{indented_result}"
                )

        return "\n\n".join(combined_results)

    parallel_delegate_to_agents.zrb_is_delegate_tool = True
    parallel_delegate_to_agents.__name__ = "DelegateToAgentsParallel"
    parallel_delegate_to_agents.__doc__ = (
        "Delegate tasks to multiple sub-agents in parallel for improved throughput.\n\n"
        "MANDATES:\n"
        "- Each sub-agent is a BLANK SLATE without your history/context. Provide ALL self-contained context (paths, rules, code).\n"
        "- User CANNOT see sub-agent outputs directly. You MUST extract and report all findings in your final response.\n"
        "- Tool approvals are processed sequentially to prevent UI conflicts.\n\n"
        "Args:\n"
        "    tasks: List of task dicts, each with:\n"
        "        - agent_name: Name of the sub-agent\n"
        "        - task: Task description\n"
        "        - additional_context: (optional) Additional context\n\n"
        f"AVAILABLE AGENTS:\n{agent_doc_section}"
    )
    return parallel_delegate_to_agents
