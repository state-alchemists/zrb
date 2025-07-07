import json
import os
from typing import Any

from zrb.config.config import CFG
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.history import ConversationHistoryData
from zrb.util.file import read_file, write_file


def read_chat_conversation(ctx: AnySharedContext) -> dict[str, Any] | list | None:
    """Reads conversation history from the session file.
    Returns the raw dictionary or list loaded from JSON, or None if not found/empty.
    The LLMTask will handle parsing this into ConversationHistoryData.
    """
    if ctx.input.start_new:
        return None  # Indicate no history to load
    previous_session_name = ctx.input.previous_session
    if not previous_session_name:  # Check for empty string or None
        last_session_file_path = os.path.join(CFG.LLM_HISTORY_DIR, "last-session")
        if os.path.isfile(last_session_file_path):
            previous_session_name = read_file(last_session_file_path).strip()
            if not previous_session_name:  # Handle empty last-session file
                return None
        else:
            return None  # No previous session specified and no last session found
    conversation_file_path = os.path.join(
        CFG.LLM_HISTORY_DIR, f"{previous_session_name}.json"
    )
    if not os.path.isfile(conversation_file_path):
        ctx.log_warning(f"History file not found: {conversation_file_path}")
        return None
    try:
        content = read_file(conversation_file_path)
        if not content.strip():
            ctx.log_warning(f"History file is empty: {conversation_file_path}")
            return None
        # Return the raw loaded data (dict or list)
        return json.loads(content)
    except json.JSONDecodeError:
        ctx.log_warning(
            f"Could not decode JSON from history file '{conversation_file_path}'. "
            "Treating as empty history."
        )
        return None
    except Exception as e:
        ctx.log_warning(
            f"Error reading history file '{conversation_file_path}': {e}. "
            "Treating as empty history."
        )
        return None


def write_chat_conversation(
    ctx: AnySharedContext, history_data: ConversationHistoryData
):
    """Writes the conversation history data (including context) to a session file."""
    os.makedirs(CFG.LLM_HISTORY_DIR, exist_ok=True)
    current_session_name = ctx.session.name
    if not current_session_name:
        ctx.log_warning("Cannot write history: Session name is empty.")
        return
    conversation_file_path = os.path.join(
        CFG.LLM_HISTORY_DIR, f"{current_session_name}.json"
    )
    try:
        # Use model_dump_json to serialize the Pydantic model
        write_file(conversation_file_path, history_data.model_dump_json(indent=2))
        # Update the last-session pointer
        last_session_file_path = os.path.join(CFG.LLM_HISTORY_DIR, "last-session")
        write_file(last_session_file_path, current_session_name)
    except Exception as e:
        ctx.log_error(f"Error writing history file '{conversation_file_path}': {e}")
