import json
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from zrb.attr.type import IntAttr
from zrb.config.llm_config import llm_config
from zrb.config.llm_rate_limitter import LLMRateLimitter
from zrb.config.llm_rate_limitter import llm_rate_limitter as default_llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.task.llm.history_list import count_token_in_history_list
from zrb.util.attr import get_int_attr

if TYPE_CHECKING:
    from pydantic_ai import ModelMessage, RunContext


def create_history_processor(
    ctx: AnyContext,
    long_message_warning_prompt: str,
    history_summarization_token_threshold: int,
) -> Callable[
    ["RunContext", list["ModelMessage"]], Coroutine[None, None, list["ModelMessage"]]
]:
    from pydantic_ai import ModelMessage, ModelRequest, RunContext
    from pydantic_ai.messages import ModelMessagesTypeAdapter, UserPromptPart

    async def inject_history_processor(
        run_ctx: RunContext[None],
        messages: list[ModelMessage],
    ) -> list[ModelMessage]:
        # TODO: Use this https://ai.pydantic.dev/message-history/#runcontext-parameter
        total_token = run_ctx.usage.total_tokens
        if total_token >= history_summarization_token_threshold:
            messages.append(
                ModelRequest(parts=[UserPromptPart(long_message_warning_prompt)])
            )
        return messages

    return inject_history_processor
