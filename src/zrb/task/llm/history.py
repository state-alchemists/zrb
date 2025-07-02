import json
import os
from collections.abc import Callable
from copy import deepcopy
from typing import Any, Optional

from pydantic import BaseModel, Field

from zrb.attr.type import StrAttr
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.typing import ListOfDict
from zrb.util.attr import get_str_attr
from zrb.util.file import read_file, write_file
from zrb.util.run import run_async


# Define the new ConversationHistoryData model
class ConversationHistoryData(BaseModel):
    long_term_context: str = Field(
        default="",
        description="A markdown-formatted string containing curated, long-term context.",
    )
    conversation_summary: str = Field(
        default="",
        description="A free-text summary of the conversation history.",
    )
    history: ListOfDict = Field(
        default_factory=list,
        description="The recent, un-summarized conversation history.",
    )

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
            if isinstance(data, dict):
                # This handles both the new format and the old {'context': ..., 'history': ...}
                return cls.model_validate(data)
            elif isinstance(data, list):
                # Handle very old format (just a list) - wrap it
                ctx.log_warning(
                    f"History from {source} contains legacy list format. "
                    "Wrapping it into the new structure. "
                    "Consider updating the source format."
                )
                return cls(history=data)
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
    conversation_history_reader: (
        Callable[[AnySharedContext], ConversationHistoryData | dict | list | None]
        | None
    ),
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
    conversation_history_writer: (
        Callable[[AnySharedContext, ConversationHistoryData], None] | None
    ),
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


def replace_system_prompt_in_history_list(
    history_list: ListOfDict, replacement: str = "<main LLM system prompt>"
) -> ListOfDict:
    """
    Returns a new history list where any part with part_kind 'system-prompt'
    has its 'content' replaced with the given replacement string.
    Args:
        history: List of history items (each item is a dict with a 'parts' list).
        replacement: The string to use in place of system-prompt content.

    Returns:
        A deep-copied list of history items with system-prompt content replaced.
    """
    new_history = deepcopy(history_list)
    for item in new_history:
        parts = item.get("parts", [])
        for part in parts:
            if part.get("part_kind") == "system-prompt":
                part["content"] = replacement
    return new_history


def count_part_in_history_list(history_list: ListOfDict) -> int:
    """Calculates the total number of 'parts' in a history list."""
    history_part_len = 0
    for history in history_list:
        if "parts" in history:
            history_part_len += len(history["parts"])
        else:
            history_part_len += 1
    return history_part_len
