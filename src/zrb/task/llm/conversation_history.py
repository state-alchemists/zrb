import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from zrb.attr.type import StrAttr
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.conversation_history_model import ConversationHistory
from zrb.task.llm.typing import ListOfDict
from zrb.util.attr import get_str_attr
from zrb.util.file import write_file
from zrb.util.run import run_async


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
        Callable[[AnySharedContext], ConversationHistory | dict | list | None] | None
    ),
    conversation_history_file_attr: StrAttr | None,
    render_history_file: bool,
    conversation_history_attr: (
        ConversationHistory
        | Callable[[AnySharedContext], ConversationHistory | dict | list]
        | dict
        | list
    ),
) -> ConversationHistory:
    """Reads conversation history from reader, file, or attribute, with validation."""
    history_file = get_history_file(
        ctx, conversation_history_file_attr, render_history_file
    )
    # Use the class method defined above
    history_data = await ConversationHistory.read_from_source(
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
        history_data = ConversationHistory.parse_and_validate(
            ctx, raw_data_attr, "attribute"
        )
        if history_data:
            return history_data
    # Fallback: Return default value
    return ConversationHistory()


async def write_conversation_history(
    ctx: AnyContext,
    history_data: ConversationHistory,
    conversation_history_writer: (
        Callable[[AnySharedContext, ConversationHistory], None] | None
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
        write_file(history_file, json.dumps(history_data.to_dict(), indent=2))


def replace_system_prompt_in_history(
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
