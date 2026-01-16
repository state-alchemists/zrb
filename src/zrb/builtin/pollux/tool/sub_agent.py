from pydantic_ai import Tool

from zrb.builtin.pollux.agent import create_agent, run_agent
from zrb.builtin.pollux.config.config import LLMConfig
from zrb.builtin.pollux.config.config import llm_config as default_config
from zrb.builtin.pollux.config.limiter import LLMLimiter
from zrb.builtin.pollux.config.limiter import llm_limiter as default_limiter
from zrb.builtin.pollux.history_manager import AnyHistoryManager, FileHistoryManager


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
) -> Tool:
    """
    Creates a Tool that invokes a sub-agent.
    The sub-agent manages its own persistent history via HistoryManager
    and handles approval via CLI fallback if needed.
    """
    config = llm_config or default_config
    limiter = llm_limitter or default_limiter
    manager = history_manager or FileHistoryManager(history_dir="~/.llm_chat/subagents")
    final_model = model or config.model

    agent = create_agent(
        model=final_model,
        system_prompt=system_prompt,
        tools=tools,
        yolo=False,
    )

    async def run_sub_agent(prompt: str) -> str:
        # Load persistent history
        history = manager.load(conversation_name)

        # Execute agent with blocking confirmation loop for approvals
        result, new_history = await run_agent(
            agent=agent,
            message=prompt,
            message_history=history,
            limiter=limiter,
        )

        # Save updated history
        manager.update(conversation_name, new_history)
        manager.save(conversation_name)

        return str(result)

    return Tool(run_sub_agent, name=name, description=description)
