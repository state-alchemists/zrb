import json
from typing import TYPE_CHECKING, Any, Callable

from zrb.attr.type import IntAttr
from zrb.config.llm_config import llm_config
from zrb.config.llm_rate_limitter import LLMRateLimitter
from zrb.config.llm_rate_limitter import llm_rate_limitter as default_llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.task.llm.history_list import count_token_in_history_list
from zrb.util.attr import get_int_attr

if TYPE_CHECKING:
    from pydantic_ai import ModelMessage


def get_long_message_token_threshold(
    ctx: AnyContext,
    long_message_token_threshold_attr: IntAttr | None,
    render_long_message_token_threshold: bool,
) -> int:
    """Gets the history summarization token threshold, handling defaults and errors."""
    try:
        return get_int_attr(
            ctx,
            long_message_token_threshold_attr,
            llm_config.default_long_message_token_threshold,
            auto_render=render_long_message_token_threshold,
        )
    except ValueError as e:
        ctx.log_warning(
            f"Could not convert long_message_token_threshold to int: {e}. "
            "Defaulting to -1 (no threshold)."
        )
        return -1


def create_long_message_warning_injector(
    long_message_warning_prompt: str,
    rate_limitter: LLMRateLimitter | None,
    threshold: int,
) -> Callable[[list["ModelMessage"]], list["ModelMessage"]]:
    from pydantic_ai import ModelMessage, ModelRequest, RunContext
    from pydantic_ai.messages import ModelMessagesTypeAdapter, UserPromptPart

    if rate_limitter is None:
        rate_limitter = default_llm_rate_limitter

    def inject_long_message_warning(
        run_ctx: RunContext[None],
        messages: list[ModelMessage],
    ) -> list[ModelMessage]:
        # TODO: Use this https://ai.pydantic.dev/message-history/#runcontext-parameter
        # print("TODO REMOVE THIS >>", run_ctx.usage.total_tokens)
        history_list: list[dict[str, Any]] = json.loads(
            ModelMessagesTypeAdapter.dump_json(messages)
        )  # noqa
        token_count = count_token_in_history_list(history_list, rate_limitter)
        if token_count >= threshold:
            messages.append(
                ModelRequest(parts=[UserPromptPart(long_message_warning_prompt)])
            )
        return messages

    return inject_long_message_warning
