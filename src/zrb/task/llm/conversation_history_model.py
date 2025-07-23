import json
import os
from collections.abc import Callable
from typing import Any

from zrb.config.llm_context.config import llm_context_config
from zrb.context.any_context import AnyContext
from zrb.task.llm.typing import ListOfDict
from zrb.util.file import read_file
from zrb.util.llm.prompt import make_prompt_section
from zrb.util.run import run_async


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
    async def read_from_source(
        cls,
        ctx: AnyContext,
        reader: Callable[[AnyContext], dict[str, Any] | list | None] | None,
        file_path: str | None,
    ) -> "ConversationHistory | None":
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
        # Fallback: Return default value
        return None

    def fetch_newest_notes(self):
        self._fetch_long_term_note()
        self._fetch_contextual_note()

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

    def write_past_conversation_summary(self, past_conversation_summary: str):
        """
        Write or update the past conversation summary.

        Use this tool to store or update a summary of previous conversations for
        future reference. This is useful for providing context to LLMs or other tools
        that need a concise history.

        Args:
            past_conversation_summary (str): The summary text to store.

        Returns:
            str: A JSON object indicating the success or failure of the operation.

        Raises:
            Exception: If the summary cannot be written.
        """
        self.past_conversation_summary = past_conversation_summary
        return json.dumps({"success": True})

    def write_past_conversation_transcript(self, past_conversation_transcript: str):
        """
        Write or update the past conversation transcript.

        Use this tool to store or update the full transcript of previous conversations.
        This is useful for providing detailed context to LLMs or for record-keeping.

        Args:
            past_conversation_transcript (str): The transcript text to store.

        Returns:
            str: A JSON object indicating the success or failure of the operation.

        Raises:
            Exception: If the transcript cannot be written.
        """
        self.past_conversation_transcript = past_conversation_transcript
        return json.dumps({"success": True})

    def read_long_term_note(self) -> str:
        """
        Read the content of the long-term references.

        This tool helps you retrieve knowledge or notes stored for long-term reference.
        If the note does not exist, you may want to create it using the write tool.

        Returns:
            str: JSON with content of the notes.

        Raises:
            Exception: If the note cannot be read.
        """
        return json.dumps({"content": self._fetch_long_term_note()})

    def write_long_term_note(self, content: str) -> str:
        """
        Write the entire content of the long-term references.
        This will overwrite any existing long-term notes.

        Args:
            content (str): The full content of the long-term notes.

        Returns:
            str: JSON indicating success.
        """
        llm_context_config.write_context(content, context_path="/")
        return json.dumps({"success": True})

    def read_contextual_note(self) -> str:
        """
        Read the content of the contextual references for the current project.

        This tool helps you retrieve knowledge or notes stored for contextual reference.
        If the note does not exist, you may want to create it using the write tool.

        Returns:
            str: JSON with content of the notes.

        Raises:
            Exception: If the note cannot be read.
        """
        return json.dumps({"content": self._fetch_contextual_note()})

    def write_contextual_note(
        self, content: str, context_path: str | None = None
    ) -> str:
        """
        Write the entire content of the contextual references for a specific path.
        This will overwrite any existing contextual notes for that path.

        Args:
            content (str): The full content of the contextual notes.
            context_path (str, optional): The directory path for the context.
                                        Defaults to the current project path.

        Returns:
            str: JSON indicating success.
        """
        if context_path is None:
            context_path = self.project_path
        llm_context_config.write_context(content, context_path=context_path)
        return json.dumps({"success": True})

    def _fetch_long_term_note(self):
        contexts = llm_context_config.get_contexts(cwd=self.project_path)
        self.long_term_note = contexts.get("/", "")
        return self.long_term_note

    def _fetch_contextual_note(self):
        contexts = llm_context_config.get_contexts(cwd=self.project_path)
        self.contextual_note = "\n".join(
            [
                make_prompt_section(header, content)
                for header, content in contexts.items()
                if header != "/"
            ]
        )
        return self.contextual_note
