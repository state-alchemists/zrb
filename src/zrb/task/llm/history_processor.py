import json
import sys
import traceback
from typing import TYPE_CHECKING, Callable, Coroutine

from zrb.config.llm_rate_limitter import LLMRateLimitter
from zrb.config.llm_rate_limitter import llm_rate_limitter as default_llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.task.llm.agent import run_agent_iteration
from zrb.util.cli.style import stylize_faint

if sys.version_info >= (3, 12):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


if TYPE_CHECKING:
    from pydantic_ai import ModelMessage, RunContext
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings


class SingleMessage(TypedDict):
    """
    SingleConversation

    Attributes:
        role: Either AI, User, Tool Call, or Tool Result
        time: yyyy-mm-dd HH:mm:ss
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


def create_history_processor(
    ctx: AnyContext,
    system_prompt: str,
    summarization_model: "Model | str | None",
    summarization_model_settings: "ModelSettings | None",
    summarization_system_prompt: str,
    history_summarization_token_threshold: int,
    rate_limitter: LLMRateLimitter | None = None,
    retries: int = 3,
) -> Callable[
    ["RunContext", list["ModelMessage"]], Coroutine[None, None, list["ModelMessage"]]
]:
    from pydantic_ai import Agent, ModelMessage, ModelRequest, RunContext
    from pydantic_ai.messages import ModelMessagesTypeAdapter, UserPromptPart

    if rate_limitter is None:
        rate_limitter = default_llm_rate_limitter

    async def inject_history_processor(
        messages: list[ModelMessage],
    ) -> list[ModelMessage]:
        history_list = json.loads(ModelMessagesTypeAdapter.dump_json(messages))
        history_list_without_instruction = [
            {key: history[key] for key in history if key != "instructions"}
            for history in history_list
        ]
        history_json_str = json.dumps(history_list_without_instruction)
        # Estimate token usage
        # Note: Pydantic ai has run context https://ai.pydantic.dev/message-history/#runcontext-parameter
        # But we cannot use run_ctx.usage.total_tokens because total token keep increasing even after summariztion.
        estimated_token_usage = rate_limitter.count_token(
            history_json_str + json.dumps({"instructions": system_prompt})
        )
        ctx.print(
            stylize_faint(
                f"  Estimated token usage/summarization threshold: {estimated_token_usage}/{history_summarization_token_threshold}"
            ),
            plain=True,
        )
        ctx.print(stylize_faint(f"  Message length: {len(messages)}"), plain=True)
        if (
            estimated_token_usage < history_summarization_token_threshold
            or len(messages) == 1
        ):
            return messages

        summarization_message = (
            f"Summarize the following conversation: {history_json_str}"
        )
        summarization_agent = Agent[None, ConversationSummary](
            model=summarization_model,
            output_type=save_conversation_summary,
            system_prompt=summarization_system_prompt,
            model_settings=summarization_model_settings,
            retries=retries,
        )
        try:
            ctx.print(stylize_faint("  📝 Rollup Conversation"), plain=True)
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
                ctx.print(
                    stylize_faint(f"  📝 Rollup Conversation Token: {usage}"),
                    plain=True,
                )
                ctx.print(plain=True)
                ctx.log_info("History summarized and updated.")
                condensed_message = (
                    "**SYSTEM INFO** Here is the summary of past conversation: "
                    f"{json.dumps(summary_run.result.output)}"
                )
                return [
                    ModelRequest(
                        instructions=system_prompt,
                        parts=[UserPromptPart(condensed_message)],
                    )
                ]
            ctx.log_warning("History summarization failed or returned no data.")
        except BaseException as e:
            ctx.log_warning(f"Error during history summarization: {e}")
            traceback.print_exc()
        return messages

    return inject_history_processor
