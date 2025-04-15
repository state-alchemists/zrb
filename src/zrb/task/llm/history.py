import json
import os
from collections.abc import Callable
from typing import Any, Optional

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.attr.type import BoolAttr, IntAttr, StrAttr
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.agent import run_agent_iteration  # Updated import
from zrb.util.attr import get_bool_attr, get_int_attr, get_str_attr
from zrb.task.llm.typing import ListOfDict
from zrb.util.file import read_file, write_file
from zrb.util.run import run_async


# Define the new ConversationHistoryData model
class ConversationHistoryData(BaseModel):
    context: dict[str, Any] = {}
    history: ListOfDict = []

    @classmethod
    async def read_from_sources(
        cls,
        ctx: AnyContext,
        reader: Callable[[AnyContext], dict[str, Any] | list | None] | None,
        file_path: str | None,
    ) -> Optional["ConversationHistoryData"]:
        """Reads conversation history from various sources with priority."""
        # Priority 1: Reader function
        if reader:
            try:
                raw_data = await run_async(reader(ctx))
                if raw_data:
                    instance = cls.parse_and_validate(ctx, raw_data, "reader")
                    if instance:
                        return instance
            except Exception as e:
                ctx.log_warning(
                    f"Error executing conversation history reader: {e}. Ignoring."
                )
        # Priority 2: History file
        if file_path and os.path.isfile(file_path):
            try:
                content = read_file(file_path)
                raw_data = json.loads(content)
                instance = cls.parse_and_validate(ctx, raw_data, f"file '{file_path}'")
                if instance:
                    return instance
            except json.JSONDecodeError:
                ctx.log_warning(
                    f"Could not decode JSON from history file '{file_path}'. "
                    "Ignoring file content."
                )
            except Exception as e:
                ctx.log_warning(
                    f"Error reading history file '{file_path}': {e}. "
                    "Ignoring file content."
                )
        # If neither reader nor file provided valid data
        return None

    @classmethod
    def parse_and_validate(
        cls, ctx: AnyContext, data: Any, source: str
    ) -> Optional["ConversationHistoryData"]:
        """Parses raw data into ConversationHistoryData, handling validation & old formats."""
        try:
            if isinstance(data, cls):
                return data  # Already a valid instance
            if isinstance(data, dict) and "history" in data:
                # Standard format {'context': ..., 'history': ...}
                # Ensure context exists, even if empty
                data.setdefault("context", {})
                return cls.model_validate(data)
            elif isinstance(data, list):
                # Handle old format (just a list) - wrap it
                ctx.log_warning(
                    f"History from {source} contains old list format. "
                    "Wrapping it into the new structure {'context': {}, 'history': [...]}. "
                    "Consider updating the source format."
                )
                return cls(history=data, context={})
            else:
                ctx.log_warning(
                    f"History data from {source} has unexpected format "
                    f"(type: {type(data)}). Ignoring."
                )
                return None
        except Exception as e:  # Catch validation errors too
            ctx.log_warning(
                f"Error validating/parsing history data from {source}: {e}. Ignoring."
            )
            return None


def get_history_file(
    ctx: AnyContext,
    conversation_history_file_attr: StrAttr | None,
    render_history_file: bool,
) -> str:
    """Gets the path to the conversation history file, rendering if configured."""
    return get_str_attr(
        ctx,
        conversation_history_file_attr,
        "",
        auto_render=render_history_file,
    )


async def read_conversation_history(
    ctx: AnyContext,
    conversation_history_reader: Callable[
        [AnySharedContext], ConversationHistoryData | dict | list | None
    ]
    | None,
    conversation_history_file_attr: StrAttr | None,
    render_history_file: bool,
    conversation_history_attr: (
        ConversationHistoryData
        | Callable[[AnySharedContext], ConversationHistoryData | dict | list]
        | dict
        | list
    ),
) -> ConversationHistoryData:
    """Reads conversation history from reader, file, or attribute, with validation."""
    history_file = get_history_file(
        ctx, conversation_history_file_attr, render_history_file
    )
    # Use the class method defined above
    history_data = await ConversationHistoryData.read_from_sources(
        ctx=ctx,
        reader=conversation_history_reader,
        file_path=history_file,
    )
    if history_data:
        return history_data
    # Priority 3: Callable or direct conversation_history attribute
    raw_data_attr: Any = None
    if callable(conversation_history_attr):
        try:
            raw_data_attr = await run_async(conversation_history_attr(ctx))
        except Exception as e:
            ctx.log_warning(
                f"Error executing callable conversation_history attribute: {e}. "
                "Ignoring."
            )
    if raw_data_attr is None:
        raw_data_attr = conversation_history_attr
    if raw_data_attr:
        # Use the class method defined above
        history_data = ConversationHistoryData.parse_and_validate(
            ctx, raw_data_attr, "attribute"
        )
        if history_data:
            return history_data
    # Fallback: Return default value
    return ConversationHistoryData()


async def write_conversation_history(
    ctx: AnyContext,
    history_data: ConversationHistoryData,
    conversation_history_writer: Callable[
        [AnySharedContext, ConversationHistoryData], None
    ]
    | None,
    conversation_history_file_attr: StrAttr | None,
    render_history_file: bool,
):
    """Writes conversation history using the writer or to a file."""
    if conversation_history_writer is not None:
        await run_async(conversation_history_writer(ctx, history_data))
    history_file = get_history_file(
        ctx, conversation_history_file_attr, render_history_file
    )
    if history_file != "":
        write_file(history_file, history_data.model_dump_json(indent=2))


def get_history_part_len(history_list: ListOfDict) -> int:
    """Calculates the total number of 'parts' in a history list."""
    history_part_len = 0
    for history in history_list:
        if "parts" in history:
            history_part_len += len(history["parts"])
        else:
            history_part_len += 1
    return history_part_len


def get_history_summarization_threshold(
    ctx: AnyContext,
    history_summarization_threshold_attr: IntAttr,
    render_history_summarization_threshold: bool,
) -> int:
    """Gets the history summarization threshold, handling defaults and errors."""
    try:
        return get_int_attr(
            ctx,
            history_summarization_threshold_attr,
            -1,  # Default to -1 (no threshold)
            auto_render=render_history_summarization_threshold,
        )
    except ValueError as e:
        ctx.log_warning(
            f"Could not convert history_summarization_threshold to int: {e}. "
            "Defaulting to -1 (no threshold)."
        )
        return -1


def should_summarize_history(
    ctx: AnyContext,
    history_list: ListOfDict,
    should_summarize_history_attr: BoolAttr,
    render_summarize_history: bool,
    history_summarization_threshold_attr: IntAttr,
    render_history_summarization_threshold: bool,
) -> bool:
    """Determines if history summarization should occur based on length and config."""
    history_part_len = get_history_part_len(history_list)
    if history_part_len == 0:
        return False
    summarization_threshold = get_history_summarization_threshold(
        ctx,
        history_summarization_threshold_attr,
        render_history_summarization_threshold,
    )
    if summarization_threshold == -1:  # -1 means no summarization trigger
        return False
    if summarization_threshold > history_part_len:
        return False
    return get_bool_attr(
        ctx,
        should_summarize_history_attr,
        False,  # Default to False if not specified
        auto_render=render_summarize_history,
    )


async def prepare_initial_state(
    ctx: AnyContext,
    conversation_history_reader: Callable[
        [AnySharedContext], ConversationHistoryData | dict | list | None
    ]
    | None,
    conversation_history_file_attr: StrAttr | None,
    render_history_file: bool,
    conversation_history_attr: (
        ConversationHistoryData
        | Callable[[AnySharedContext], ConversationHistoryData | dict | list]
        | dict
        | list
    ),
    conversation_context_getter: Callable[[AnyContext], dict[str, Any]],
) -> tuple[ListOfDict, dict[str, Any]]:
    """Reads history and prepares the initial conversation context."""
    history_data: ConversationHistoryData = await read_conversation_history(
        ctx,
        conversation_history_reader,
        conversation_history_file_attr,
        render_history_file,
        conversation_history_attr,
    )
    history_list = history_data.history
    conversation_context = conversation_context_getter(ctx)
    # Merge history context from loaded data without overwriting existing keys
    for key, value in history_data.context.items():
        if key not in conversation_context:
            conversation_context[key] = value
    return history_list, conversation_context


class SummarizationConfig(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    model: Model | str | None = None
    settings: ModelSettings | None = None
    prompt: str
    retries: int = 1


async def summarize_history(
    ctx: AnyContext,
    config: SummarizationConfig,
    conversation_context: dict[str, Any],
    history_list: ListOfDict,
) -> dict[str, Any]:
    """Runs an LLM call to summarize history and update the context."""
    ctx.log_info("Attempting to summarize conversation history...")

    summarization_agent = Agent(
        model=config.model,
        system_prompt=config.prompt,
        tools=[],  # No tools needed for summarization
        mcp_servers=[],
        model_settings=config.settings,
        retries=config.retries,
    )

    # Prepare context and history for summarization prompt
    try:
        context_json = json.dumps(conversation_context)
        history_to_summarize_json = json.dumps(history_list)
        summarization_user_prompt = (
            f"# Current Context\n{context_json}\n\n"
            f"# Conversation History to Summarize\n{history_to_summarize_json}"
        )
    except Exception as e:
        ctx.log_warning(f"Error formatting context/history for summarization: {e}")
        return conversation_context  # Return original context if formatting fails

    try:
        summary_run = await run_agent_iteration(
            ctx=ctx,
            agent=summarization_agent,
            user_prompt=summarization_user_prompt,
            history_list=[],  # Summarization agent doesn't need prior history
        )
        if summary_run and summary_run.result.data:
            summary_text = str(summary_run.result.data)
            # Update context with the new summary
            conversation_context["history_summary"] = summary_text
            ctx.log_info("History summarized and added/updated in context.")
            ctx.log_info(f"Conversation summary: {summary_text}")
        else:
            ctx.log_warning("History summarization failed or returned no data.")
    except Exception as e:
        ctx.log_warning(f"Error during history summarization: {e}")

    return conversation_context


async def maybe_summarize_history(
    ctx: AnyContext,
    history_list: ListOfDict,
    conversation_context: dict[str, Any],
    should_summarize_history_attr: BoolAttr,
    render_summarize_history: bool,
    history_summarization_threshold_attr: IntAttr,
    render_history_summarization_threshold: bool,
    model: str | Model | None,
    model_settings: ModelSettings | None,
    summarization_prompt: str,
) -> tuple[ListOfDict, dict[str, Any]]:
    """Summarizes history and updates context if enabled and threshold met."""
    if should_summarize_history(
        ctx,
        history_list,
        should_summarize_history_attr,
        render_summarize_history,
        history_summarization_threshold_attr,
        render_history_summarization_threshold,
    ):
        # Use summarize_history defined above
        updated_context = await summarize_history(
            ctx=ctx,
            config=SummarizationConfig(
                model=model,
                settings=model_settings,
                prompt=summarization_prompt,
            ),
            conversation_context=conversation_context,
            history_list=history_list,  # Pass the full list for context
        )
        # Truncate the history list after summarization
        return [], updated_context
    return history_list, conversation_context
