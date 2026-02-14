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
        # 1. Load Agent
        sub_agent = sub_agent_manager.create_agent(agent_name)
        if not sub_agent:
            return f"Error: Sub-agent '{agent_name}' not found."

        # 2. Prepare Message
        full_message = task
        if additional_context:
            full_message = f"{task}\n\nContext:\n{additional_context}"

        # 3. Setup Indented UI
        parent_ui = current_ui.get() or StdUI()
        indented_ui = IndentedUI(parent_ui)

        # 4. Run Agent
        try:
            # FORCE NEWLINE directly to stderr to guarantee visual separation
            result, _ = await run_agent(
                agent=sub_agent,
                message=full_message,
                message_history=[],  # Isolated history
                limiter=llm_limiter,  # Shared limiter
                ui=indented_ui,
            )

            # Format the final result with indentation
            indented_result = "\n".join(["  " + line for line in result.splitlines()])
            # Return the result without a leading newline to prevent extra gaps
            return (
                f"Sub-agent '{agent_name}' completed the task:\n\n{indented_result}\n"
            )

        except Exception as e:
            return f"Error executing sub-agent '{agent_name}': {e}"

    delegate_to_agent.__name__ = "DelegateToAgent"
    delegate_to_agent.__doc__ = (
        "Delegates a complex task to a specialized sub-agent. "
        "\n\n**OPERATIONAL MANDATE:**"
        "\n- The sub-agent is a **BLANK SLATE**. It does NOT share your history or system context."
        "\n- You MUST ALWAYS provide full, self-contained context: paths, code snippets, architectural rules, and OS/CWD details."
        "\n- Use ONLY for multi-step research or specialized analysis that would pollute your primary context."
        "\n\n**AVAILABLE AGENTS:**\n"
        f"{agent_doc_section}"
        "\n\n**ARGS:**"
        "\n- `agent_name`: The name of the sub-agent to activate."
        "\n- `task`: The specific, detailed instruction for the sub-agent."
        "\n- `additional_context`: MANDATORY self-contained context required for the task."
    )
    return delegate_to_agent
