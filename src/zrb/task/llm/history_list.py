import json

from zrb.config.llm_rate_limitter import LLMRateLimitter
from zrb.config.llm_rate_limitter import llm_rate_limitter as default_llm_rate_limitter
from zrb.task.llm.typing import ListOfDict


def count_token_in_history_list(
    history_list: ListOfDict, llm_rate_limitter: LLMRateLimitter | None = None
) -> int:
    """Counts the total number of tokens in a conversation history list."""
    history_list_without_repeating_instruction = []
    for idx, history in enumerate(history_list):
        # Only preserve instruction in last history
        history_list_without_repeating_instruction.append(
            {
                key: history[key]
                for key in history
                if key != "instructions" or idx == len(history_list) - 1
            }
        )
    text_to_count = json.dumps(history_list_without_repeating_instruction)
    if llm_rate_limitter is None:
        llm_rate_limitter = default_llm_rate_limitter
    return llm_rate_limitter.count_token(text_to_count)
