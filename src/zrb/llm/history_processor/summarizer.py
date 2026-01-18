from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.config.config import CFG
from zrb.llm.agent.summarizer import create_summarizer_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.config.limiter import llm_limiter as default_llm_limiter
from zrb.util.markdown import make_markdown_section

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage


def is_turn_start(msg: Any) -> bool:
    """Identify start of a new user interaction (User Prompt without Tool Return)."""
    from pydantic_ai.messages import ModelRequest, ToolReturnPart, UserPromptPart

    if not isinstance(msg, ModelRequest):
        return False
    # In pydantic_ai, ModelRequest parts can be list of various parts
    has_user = any(isinstance(p, UserPromptPart) for p in msg.parts)
    has_return = any(isinstance(p, ToolReturnPart) for p in msg.parts)
    return has_user and not has_return


async def summarize_history(
    messages: "list[ModelMessage]",
    agent: Any = None,
    summary_window: int | None = None,
) -> "list[ModelMessage]":
    """
    Summarizes the history, keeping the last `summary_window` messages intact.
    Returns a new list of messages where older messages are replaced by a summary.
    """
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    if summary_window is None:
        summary_window = CFG.LLM_HISTORY_SUMMARIZATION_WINDOW
    if len(messages) <= summary_window:
        return messages

    # Determine split index
    # We want to keep at least summary_window messages.
    # So split_idx <= len(messages) - summary_window.
    # We search backwards from there for a clean turn start.
    start_search_idx = max(0, len(messages) - summary_window)
    split_idx = -1

    # Iterate backwards from start_search_idx to 0
    for i in range(start_search_idx, -1, -1):
        if is_turn_start(messages[i]):
            split_idx = i
            break

    if split_idx <= 0:
        return messages

    to_summarize = messages[:split_idx]
    to_keep = messages[split_idx:]

    # Simple text representation for now
    history_text = "\n".join([str(m) for m in to_summarize])

    summarizer_agent = agent or create_summarizer_agent()

    # Run the summarizer agent
    result = await summarizer_agent.run(
        f"Summarize this conversation history:\n{history_text}"
    )
    summary_text = result.data

    # Create a summary message injected as user context
    summary_message = ModelRequest(
        parts=[
            UserPromptPart(
                content=make_markdown_section(
                    "Previous conversation summary", summary_text
                )
            )
        ]
    )

    return [summary_message] + to_keep


def create_summarizer_history_processor(
    agent: Any = None,
    limiter: LLMLimiter | None = None,
    token_threshold: int | None = None,
    summary_window: int | None = None,
) -> "Callable[[list[ModelMessage]], Awaitable[list[ModelMessage]]]":
    """
    Creates a history processor that auto-summarizes history when it exceeds `token_threshold`.
    """
    llm_limiter = limiter or default_llm_limiter
    if token_threshold is None:
        token_threshold = CFG.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD

    async def process_history(messages: "list[ModelMessage]") -> "list[ModelMessage]":
        current_tokens = llm_limiter.count_tokens(messages)

        if current_tokens <= token_threshold:
            return messages

        return await summarize_history(messages, agent, summary_window)

    return process_history
