from typing import Any

from zrb.llm.agent import create_agent, run_agent
from zrb.llm.config.config import LLMConfig
from zrb.llm.config.config import llm_config as default_config
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.config.limiter import llm_limiter as default_limiter
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.history_manager.file_history_manager import FileHistoryManager


def create_sub_agent_tool(
    name: str,
    description: str,
    model: str | None = None,
    system_prompt: str = "",
    tools: list = [],
    llm_config: LLMConfig | None = None,
    llm_limitter: LLMLimiter | None = None,
    history_manager: AnyHistoryManager | None = None,
    conversation_name: str = "sub_agent_default",
) -> Any:
    """
    Creates a Tool that invokes a sub-agent.
    The sub-agent manages its own persistent history via HistoryManager
    and handles approval via CLI fallback if needed.
    """
    config = llm_config or default_config
    limiter = llm_limitter or default_limiter
    manager = history_manager or FileHistoryManager(history_dir="~/.llm_chat/subagents")
    final_model = model or config.model

    agent_instance = None

    async def run_sub_agent(prompt: str) -> str:
        nonlocal agent_instance
        if agent_instance is None:
            agent_instance = create_agent(
                model=final_model,
                system_prompt=system_prompt,
                tools=tools,
                yolo=False,
            )

        # Load persistent history
        history = manager.load(conversation_name)

        # Execute agent with blocking confirmation loop for approvals
        # Visibility and UI inheritance are handled automatically by run_agent via ContextVar
        result, new_history = await run_agent(
            agent=agent_instance,
            message=prompt,
            message_history=history,
            limiter=limiter,
        )

        # Save updated history
        manager.update(conversation_name, new_history)
        manager.save(conversation_name)

        return str(result)

    run_sub_agent.__name__ = name
    run_sub_agent.__doc__ = (
        f"DELEGATION TOOL: {description}\n\n"
        "Use this tool to delegate complex, multi-step sub-tasks to a specialized agent. "
        "The sub-agent has its own memory and can perform its own tool calls."
        "\n\n**ARGS:**"
        "\n- `prompt`: The clear and detailed objective or instruction for the sub-agent."
    )
    return run_sub_agent
