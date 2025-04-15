import json
import os
from collections.abc import Callable
from typing import Any, Optional

from pydantic import BaseModel

from zrb.attr.type import StrAttr
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.typing import ListOfDict
from zrb.util.attr import get_str_attr
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


async def prepare_initial_state(
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
    # Clean the history list to remove context from historical user prompts
    cleaned_history_list = []
    for interaction in history_data.history:
        cleaned_history_list.append(
            remove_context_from_interaction_history(interaction)
        )
    conversation_context = conversation_context_getter(ctx)
    # Merge history context from loaded data without overwriting existing keys
    for key, value in history_data.context.items():
        if key not in conversation_context:
            conversation_context[key] = value
    # Return the CLEANED history list
    return cleaned_history_list, conversation_context


def remove_context_from_interaction_history(
    interaction: dict[str, Any],
) -> dict[str, Any]:
    try:
        cleaned_interaction = json.loads(json.dumps(interaction))
    except Exception:
        # Fallback to shallow copy if not JSON serializable (less safe)
        cleaned_interaction = interaction.copy()
    if "parts" in cleaned_interaction and isinstance(
        cleaned_interaction["parts"], list
    ):
        for part in cleaned_interaction["parts"]:
            is_user_prompt = part.get("part_kind") == "user-prompt"
            has_str_content = isinstance(part.get("content"), str)
            if is_user_prompt and has_str_content:
                content = part["content"]
                user_message_marker = "# User Message\n"
                marker_index = content.find(user_message_marker)
                if marker_index != -1:
                    # Extract message after the marker and strip whitespace
                    start_index = marker_index + len(user_message_marker)
                    part["content"] = content[start_index:].strip()
                # else: If marker not found, leave content as is (old format/error)
    return cleaned_interaction
