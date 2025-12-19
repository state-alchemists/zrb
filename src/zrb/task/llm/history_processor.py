import json
import sys
import traceback
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from zrb.config.llm_config import llm_config
from zrb.config.llm_rate_limitter import LLMRateLimitter
from zrb.config.llm_rate_limitter import llm_rate_limitter as default_llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.task.llm.agent_runner import run_agent_iteration
from zrb.util.cli.style import stylize_faint
from zrb.util.markdown import make_markdown_section

if sys.version_info >= (3, 12):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


if TYPE_CHECKING:
    from pydantic_ai import ModelMessage
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings


class SingleMessage(TypedDict):
    """
    SingleConversation

    Attributes:
        role: Either AI, User, Tool Call, or Tool Result
        time: yyyy-mm-ddTHH:MM:SSZ:
        content: The content of the message (summarize if too long)
    """

    role: str
    time: str
    content: str


class ConversationSummary(TypedDict):
    """
    Conversation history

    Attributes:
        transcript: Several last transcript of the conversation
        summary: Descriptive conversation summary
    """

    transcript: list[SingleMessage]
    summary: str


def save_conversation_summary(conversation_summary: ConversationSummary):
    """
    Write conversation summary for main assistant to continue conversation.
    """
    return conversation_summary


def create_summarize_history_processor(
    ctx: AnyContext,
    system_prompt: str,
    rate_limitter: LLMRateLimitter | None = None,
    summarization_model: "Model | str | None" = None,
    summarization_model_settings: "ModelSettings | None" = None,
    summarization_system_prompt: str | None = None,
    summarization_token_threshold: int | None = None,
    summarization_retries: int = 2,
) -> Callable[[list["ModelMessage"]], Coroutine[None, None, list["ModelMessage"]]]:
    from pydantic_ai import Agent, ModelMessage, ModelRequest
    from pydantic_ai.messages import ModelMessagesTypeAdapter, UserPromptPart

    if rate_limitter is None:
        rate_limitter = default_llm_rate_limitter
    if summarization_model is None:
        summarization_model = llm_config.default_small_model
    if summarization_model_settings is None:
        summarization_model_settings = llm_config.default_small_model_settings
    if summarization_system_prompt is None:
        summarization_system_prompt = llm_config.default_summarization_prompt
    if summarization_token_threshold is None:
        summarization_token_threshold = (
            llm_config.default_history_summarization_token_threshold
        )

    async def maybe_summarize_history(
        messages: list[ModelMessage],
    ) -> list[ModelMessage]:
        # 1. Prune History (Tool Output Pruning)
        # We prune tool outputs from messages older than the last N turns to save tokens
        # without losing the fact that the tool was called.
        messages = _prune_history(messages)

        history_list = json.loads(ModelMessagesTypeAdapter.dump_json(messages))
        history_json_str = json.dumps(history_list)
        estimated_token_usage = rate_limitter.count_token(history_json_str)

        _print_request_info(
            ctx, estimated_token_usage, summarization_token_threshold, messages
        )

        if estimated_token_usage < summarization_token_threshold or len(messages) <= 1:
            return messages

        # 2. Split Point Preservation
        # Instead of summarizing everything, we keep the recent context verbatim.
        # We target summarizing only the older portion (e.g., first 70%).
        split_index = _find_split_point(messages, rate_limitter, estimated_token_usage)

        # If split point is 0 or all messages, fallback to full summarization logic or skip
        if split_index == 0:
            return messages

        messages_to_summarize = messages[:split_index]
        messages_to_keep = messages[split_index:]

        # Prepare for summarization
        history_to_summarize_list = json.loads(
            ModelMessagesTypeAdapter.dump_json(messages_to_summarize)
        )

        # Remove 'instructions' from the history to be summarized to save tokens/confusion
        history_list_without_instruction = [
            {
                key: obj[key]
                for key in obj
                if index == len(history_to_summarize_list) - 1 or key != "instructions"
            }
            for index, obj in enumerate(history_to_summarize_list)
        ]

        history_json_str_without_instruction = json.dumps(
            history_list_without_instruction
        )
        summarization_message = f"Summarize the following conversation: {history_json_str_without_instruction}"

        summarization_agent = Agent[None, ConversationSummary](
            model=summarization_model,
            output_type=save_conversation_summary,
            instructions=summarization_system_prompt,
            model_settings=summarization_model_settings,
            retries=summarization_retries,
        )

        try:
            _print_info(ctx, "📝 Rollup Conversation", 2)
            summary_run = await run_agent_iteration(
                ctx=ctx,
                agent=summarization_agent,
                user_prompt=summarization_message,
                attachments=[],
                history_list=[],
                rate_limitter=rate_limitter,
                log_indent_level=2,
            )

            if summary_run and summary_run.result and summary_run.result.output:
                usage = summary_run.result.usage()
                _print_info(ctx, f"📝 Rollup Conversation Token: {usage}", 2)
                ctx.print(plain=True)
                ctx.log_info("History summarized and updated.")

                condensed_message = make_markdown_section(
                    header="Past Conversation",
                    content="\n".join(
                        [
                            make_markdown_section(
                                "Summary", _extract_summary(summary_run.result.output)
                            ),
                            make_markdown_section(
                                "Past Transcript (Summarized Part)",
                                _extract_transcript(summary_run.result.output),
                            ),
                        ]
                    ),
                )

                # Construct the new history:
                # [System Prompt (carried via ModelRequest usually, but here likely implicit or handled by caller)]
                # [User Message with Summary]
                # [Verbatim Recent Messages]

                # Note: The original code returned [ModelRequest(...parts=[UserPromptPart(condensed_message)])]
                # implying it replaced the WHOLE history with one message.
                # Now we want to prepend this summary message to `messages_to_keep`.

                summary_request = ModelRequest(
                    parts=[UserPromptPart(condensed_message)]
                )

                # Ensure we don't lose the system prompt if it was attached to the first message of 'messages_to_summarize'
                # In Pydantic AI, system prompt is often in the first ModelRequest.
                # The `summary_request` we created above doesn't have `instructions` set?
                # The original code set `instructions=system_prompt`. We should probably do that
                # if the first message in `messages_to_keep` doesn't have it, OR just put it on the summary request.
                # Let's put it on the summary request to be safe.

                summary_request = ModelRequest(
                    instructions=system_prompt,
                    parts=[UserPromptPart(condensed_message)],
                )

                return [summary_request] + messages_to_keep

            ctx.log_warning("History summarization failed or returned no data.")
        except BaseException as e:
            ctx.log_warning(f"Error during history summarization: {e}")
            traceback.print_exc()

        return messages

    return maybe_summarize_history


def _prune_history(messages: list["ModelMessage"]) -> list["ModelMessage"]:
    # Simple pruning: replace ToolReturn content with [PRUNED] for messages older than N
    # Pydantic AI messages structure:
    # ModelRequest(parts=[UserPromptPart, ToolReturnPart, ...])
    # ModelResponse(parts=[TextPart, ToolCallPart, ...])

    # We want to keep the last, say, 10 turns (interactions).
    # A "turn" is roughly a Request-Response pair.

    PRUNE_PROTECTED_COUNT = 10

    if len(messages) <= PRUNE_PROTECTED_COUNT:
        return messages

    import copy

    from pydantic_ai.messages import ModelRequest, ToolReturnPart

    # Deep copy to avoid mutating the original list if checking logic fails later
    new_messages = copy.deepcopy(messages)

    # Indices to prune: 0 to length - PRUNE_PROTECTED_COUNT
    prune_end_index = len(new_messages) - PRUNE_PROTECTED_COUNT

    for i in range(prune_end_index):
        msg = new_messages[i]
        if isinstance(msg, ModelRequest):
            for j, part in enumerate(msg.parts):
                if isinstance(part, ToolReturnPart):
                    # Prune content.
                    # Note: ToolReturnPart content can be Any. We assume string or serializable.
                    # We replace it with a string marker.
                    # We create a new part to replace the old one (or modify in place if mutable)
                    # Pydantic models are often immutable, so replace the part.

                    # Hack: assuming we can replace the content.
                    # If immutable, we need to construct a new ToolReturnPart.
                    # Let's try to construct a new one.

                    new_part = ToolReturnPart(
                        tool_name=part.tool_name,
                        content="[TOOL OUTPUT PRUNED]",
                        tool_call_id=part.tool_call_id,
                        timestamp=part.timestamp,
                    )
                    msg.parts[j] = new_part

    return new_messages


def _find_split_point(
    messages: list["ModelMessage"], rate_limitter: Any, total_tokens: int
) -> int:
    # Strategy: Keep last 30% of tokens.
    PRESERVE_RATIO = 0.3
    target_keep_tokens = total_tokens * PRESERVE_RATIO

    current_keep_tokens = 0
    from pydantic_ai.messages import ModelMessagesTypeAdapter

    # Iterate backwards
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        # Estimate token for this message
        # Use simple dump to string for estimation
        msg_json = json.dumps(json.loads(ModelMessagesTypeAdapter.dump_json([msg])))
        tokens = rate_limitter.count_token(msg_json)

        current_keep_tokens += tokens
        if current_keep_tokens >= target_keep_tokens:
            # We found the point where we have enough tokens to keep.
            # So split should be at i.
            # However, we should try to align with turn boundaries if possible.
            # For now, simple index is fine.
            return max(1, i)  # Ensure we summarize at least something (index > 0)

    return 0  # Should not happen if total_tokens > 0


def _print_request_info(
    ctx: AnyContext,
    estimated_token_usage: int,
    summarization_token_threshold: int,
    messages: list["ModelMessage"],
):
    _print_info(ctx, f"Current request token (estimated): {estimated_token_usage}")
    _print_info(ctx, f"Summarization token threshold: {summarization_token_threshold}")
    _print_info(ctx, f"History length: {len(messages)}")


def _print_info(ctx: AnyContext, text: str, log_indent_level: int = 0):
    log_prefix = (2 * (log_indent_level + 1)) * " "
    ctx.print(stylize_faint(f"{log_prefix}{text}"), plain=True)


def _extract_summary(summary_result_output: dict[str, Any] | str) -> str:
    summary = (
        summary_result_output.get("summary", "")
        if isinstance(summary_result_output, dict)
        else ""
    )
    return summary


def _extract_transcript(summary_result_output: dict[str, Any] | str) -> str:
    transcript_list = (
        summary_result_output.get("transcript", [])
        if isinstance(summary_result_output, dict)
        else []
    )
    transcript_list = [] if not isinstance(transcript_list, list) else transcript_list
    return "\n".join(_format_transcript_message(message) for message in transcript_list)


def _format_transcript_message(message: dict[str, str]) -> str:
    role = message.get("role", "Message")
    time = message.get("time", "<unknown>")
    content = message.get("content", "<empty>")
    return f"{role} ({time}): {content}"
