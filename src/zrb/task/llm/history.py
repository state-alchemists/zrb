import json
import os
from collections.abc import Callable
from typing import Any, Optional

from pydantic import BaseModel

from zrb.context.any_context import AnyContext
from zrb.util.file import read_file
from zrb.util.run import run_async

ListOfDict = list[dict[str, Any]]


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
        attribute_value: Any,
        default_value: "ConversationHistoryData",
    ) -> "ConversationHistoryData":
        """Reads conversation history from various sources with priority."""
        # Priority 1: Reader function
        if reader:
            try:
                raw_data = await run_async(reader(ctx))
                if raw_data:
                    instance = cls._parse_and_validate(ctx, raw_data, "reader")
                    if instance:
                        return instance
            except Exception as e:
                ctx.log_warning(f"Error executing conversation history reader: {e}. Ignoring.")
        # Priority 2: History file
        if file_path and os.path.isfile(file_path):
            try:
                content = read_file(file_path)
                raw_data = json.loads(content)
                instance = cls._parse_and_validate(ctx, raw_data, f"file '{file_path}'")
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
        # Priority 3: Callable or direct conversation_history attribute
        raw_data_attr: Any = None
        if callable(attribute_value):
            try:
                raw_data_attr = attribute_value(ctx)
            except Exception as e:
                ctx.log_warning(
                    f"Error executing callable conversation_history attribute: {e}. "
                    "Ignoring."
                )
        else:
            raw_data_attr = attribute_value
        if raw_data_attr:
            instance = cls._parse_and_validate(ctx, raw_data_attr, "attribute")
            if instance:
                return instance
        # Fallback: Return default value
        return default_value

    @classmethod
    def _parse_and_validate(
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