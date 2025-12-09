import json
from typing import TYPE_CHECKING, Any, Callable

from zrb.config.llm_rate_limitter import LLMRateLimitter
from zrb.config.llm_rate_limitter import llm_rate_limitter as default_llm_rate_limitter
from zrb.task.llm.history_list import count_token_in_history_list

if TYPE_CHECKING:
    from pydantic_ai import ModelMessage


def create_message_length_warning_injector(
    warning: str,
    rate_limitter: LLMRateLimitter | None = None,
    threshold: int | None = None,
) -> Callable[[list["ModelMessage"]], list["ModelMessage"]]:
    from pydantic_ai import ModelMessage, ModelRequest
    from pydantic_ai.messages import ModelMessagesTypeAdapter, UserPromptPart

    if rate_limitter is None:
        rate_limitter = default_llm_rate_limitter
    if threshold is None:
        threshold = round(
            min(
                rate_limitter.max_tokens_per_request,
                rate_limitter.max_tokens_per_minute,
            )
            * 0.75
        )

    def message_length_warning_injector(
        messages: list[ModelMessage],
    ) -> list[ModelMessage]:
        history_list: list[dict[str, Any]] = json.loads(
            ModelMessagesTypeAdapter.dump_json(messages)
        )  # noqa
        token_count = count_token_in_history_list(history_list, rate_limitter)
        if token_count >= threshold:
            messages.append(ModelRequest(parts=[UserPromptPart(warning)]))
        return messages

    return message_length_warning_injector
