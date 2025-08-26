import json
import os
from typing import Any

from zrb.context.any_context import AnyContext
from zrb.task.llm.typing import ListOfDict


class ConversationHistory:

    def __init__(
        self,
        past_conversation_summary: str = "",
        past_conversation_transcript: str = "",
        history: ListOfDict | None = None,
        contextual_note: str | None = None,
        long_term_note: str | None = None,
        project_path: str | None = None,
    ):
        self.past_conversation_transcript = past_conversation_transcript
        self.past_conversation_summary = past_conversation_summary
        self.history = history if history is not None else []
        self.contextual_note = contextual_note if contextual_note is not None else ""
        self.long_term_note = long_term_note if long_term_note is not None else ""
        self.project_path = project_path if project_path is not None else os.getcwd()

    def to_dict(self) -> dict[str, Any]:
        return {
            "past_conversation_summary": self.past_conversation_summary,
            "past_conversation_transcript": self.past_conversation_transcript,
            "history": self.history,
            "contextual_note": self.contextual_note,
            "long_term_note": self.long_term_note,
        }

    def model_dump_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def parse_and_validate(
        cls, ctx: AnyContext, data: Any, source: str
    ) -> "ConversationHistory":
        try:
            if isinstance(data, cls):
                return data  # Already a valid instance
            if isinstance(data, dict):
                # This handles both the new format and the old {'context': ..., 'history': ...}
                return cls(
                    past_conversation_summary=data.get("past_conversation_summary", ""),
                    past_conversation_transcript=data.get(
                        "past_conversation_transcript", ""
                    ),
                    history=data.get("history", data.get("messages", [])),
                    contextual_note=data.get("contextual_note", ""),
                    long_term_note=data.get("long_term_note", ""),
                )
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
        except Exception as e:  # Catch validation errors too
            ctx.log_warning(
                f"Error validating/parsing history data from {source}: {e}. Ignoring."
            )
        return cls()
