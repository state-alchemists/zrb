import json
import os
from collections.abc import Callable
from typing import Any

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.task.llm.typing import ListOfDict
from zrb.util.file import read_file, read_file_with_line_numbers, write_file
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

    @classmethod
    async def read_from_source(
        cls,
        ctx: AnyContext,
        reader: Callable[[AnyContext], dict[str, Any] | list | None] | None,
        file_path: str | None,
    ) -> "ConversationHistory":
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

    def _fetch_newest_notes(self):
        long_term_note_path = self._get_long_term_note_path()
        if os.path.isfile(long_term_note_path):
            self.long_term_note_path = read_file(long_term_note_path)
        contextual_note_path = self._get_contextual_note_path()
        if os.path.isfile(contextual_note_path):
            self._get_contextual_note_path = read_file(contextual_note_path)

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
            None

        Raises:
            Exception: If the summary cannot be written.
        """
        self.past_conversation_summary = past_conversation_summary

    def write_past_conversation_transcript(self, past_conversation_transcript: str):
        """
        Write or update the past conversation transcript.

        Use this tool to store or update the full transcript of previous conversations.
        This is useful for providing detailed context to LLMs or for record-keeping.

        Args:
            past_conversation_transcript (str): The transcript text to store.

        Returns:
            None

        Raises:
            Exception: If the transcript cannot be written.
        """
        self.past_conversation_transcript = past_conversation_transcript

    def read_long_term_note(
        self,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """
        Read the content of the long-term note, optionally for a specific line range.

        This tool helps you retrieve knowledge or notes stored for long-term reference.
        If the note does not exist, you may want to create it using the write tool.

        Args:
            start_line (int, optional): 1-based line number to start reading from.
            end_line (int, optional): 1-based line number to stop reading at (inclusive).

        Returns:
            str: JSON with file path, content (with line numbers), start/end lines,
                and total lines.

        Raises:
            Exception: If the note cannot be read.
                Suggests writing the note if it does not exist.
        """
        return self._read_note(
            self._get_long_term_note_path(),
            start_line,
            end_line,
            note_type="long-term note",
        )

    def write_long_term_note(self, content: str) -> str:
        """
        Write or overwrite the content of the long-term note.

        Use this tool to create a new long-term note or replace its entire content.
        Always read the note first to avoid accidental data loss, unless you are sure
        you want to overwrite.

        Args:
            content (str): The full content to write to the note.

        Returns:
            str: JSON indicating success and the note path.

        Raises:
            Exception: If the note cannot be written. Suggests checking permissions or path.
        """
        self.long_term_note = content
        return self._write_note(
            self._get_long_term_note_path(), content, note_type="long-term note"
        )

    def replace_in_long_term_note(
        self,
        old_string: str,
        new_string: str,
    ) -> str:
        """
        Replace the first occurrence of a string in the long-term note.

        Use this tool to update a specific part of the long-term note without
        overwriting the entire content. If the note does not exist, consider writing it
        first. If the string is not found, check your input or read the note to verify.

        Args:
            old_string (str): The exact string to search for and replace.
            new_string (str): The string to replace with.

        Returns:
            str: JSON indicating success and the note path.

        Raises:
            Exception: If the note does not exist or the string is not found.
                Suggests writing or reading the note.
        """
        result = self._replace_in_note(
            self._get_long_term_note_path(),
            old_string,
            new_string,
            note_type="long-term note",
        )
        self.long_term_note = new_string
        return result

    def read_contextual_note(
        self,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """
        Read the content of the contextual note, optionally for a specific line range.

        This tool helps you retrieve project-specific or session-specific notes.
        If the note does not exist, you may want to create it using the write tool.

        Args:
            start_line (int, optional): 1-based line number to start reading from.
            end_line (int, optional): 1-based line number to stop reading at (inclusive).

        Returns:
            str: JSON with file path, content (with line numbers), start/end lines,
                and total lines.

        Raises:
            Exception: If the note cannot be read.
                Suggests writing the note if it does not exist.
        """
        return self._read_note(
            self._get_contextual_note_path(),
            start_line,
            end_line,
            note_type="contextual note",
        )

    def write_contextual_note(self, content: str) -> str:
        """
        Write or overwrite the content of the contextual note.

        Use this tool to create a new contextual note or replace its entire content.
        Always read the note first to avoid accidental data loss, unless you are sure
        you want to overwrite.

        Args:
            content (str): The full content to write to the note.

        Returns:
            str: JSON indicating success and the note path.

        Raises:
            Exception: If the note cannot be written. Suggests checking permissions or path.
        """
        self.contextual_note = content
        return self._write_note(
            self._get_contextual_note_path(), content, note_type="contextual note"
        )

    def replace_in_contextual_note(
        self,
        old_string: str,
        new_string: str,
    ) -> str:
        """
        Replace the first occurrence of a string in the contextual note.

        Use this tool to update a specific part of the contextual note without
        overwriting the entire content. If the note does not exist, consider writing it
        first. If the string is not found, check your input or read the note to verify.

        Args:
            old_string (str): The exact string to search for and replace.
            new_string (str): The string to replace with.

        Returns:
            str: JSON indicating success and the note path.

        Raises:
            Exception: If the note does not exist or the string is not found.
                Suggests writing or reading the note.
        """
        result = self._replace_in_note(
            self._get_contextual_note_path(),
            old_string,
            new_string,
            note_type="contextual note",
        )
        self.contextual_note = new_string
        return result

    def _get_long_term_note_path(self) -> str:
        return os.path.abspath(os.path.expanduser(CFG.LLM_LONG_TERM_NOTE_PATH))

    def _get_contextual_note_path(self) -> str:
        return os.path.join(self.project_path, CFG.LLM_CONTEXTUAL_NOTE_FILE)

    def _read_note(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        note_type: str = "note",
    ) -> str:
        """
        Internal helper to read a note file with line numbers and error handling.
        """
        if not os.path.exists(path):
            raise Exception(
                (
                    f"{note_type.capitalize()} not found. "
                    f"Consider writing a new {note_type} first."
                )
            )
        try:
            content = read_file_with_line_numbers(path)
            lines = content.splitlines()
            total_lines = len(lines)
            start_idx = (start_line - 1) if start_line is not None else 0
            end_idx = end_line if end_line is not None else total_lines
            if start_idx < 0:
                start_idx = 0
            if end_idx > total_lines:
                end_idx = total_lines
            if start_idx > end_idx:
                start_idx = end_idx
            selected_lines = lines[start_idx:end_idx]
            content_result = "\n".join(selected_lines)
            return json.dumps(
                {
                    "path": path,
                    "content": content_result,
                    "start_line": start_idx + 1,
                    "end_line": end_idx,
                    "total_lines": total_lines,
                }
            )
        except Exception:
            raise Exception(
                f"Failed to read the {note_type}. "
                f"If the {note_type} does not exist, try writing it first."
            )

    def _write_note(self, path: str, content: str, note_type: str = "note") -> str:
        """
        Internal helper to write a note file with error handling.
        """
        try:
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            write_file(path, content)
            return json.dumps({"success": True, "path": path})
        except (OSError, IOError):
            raise Exception(
                f"Failed to write the {note_type}. "
                "Please check if the path is correct and you have write permissions."
            )
        except Exception:
            raise Exception(
                f"Unexpected error while writing the {note_type}. "
                "Please check your input and try again."
            )

    def _replace_in_note(
        self, path: str, old_string: str, new_string: str, note_type: str = "note"
    ) -> str:
        """
        Internal helper to replace a string in a note file with error handling.
        """
        if not os.path.exists(path):
            raise Exception(
                (
                    f"{note_type.capitalize()} not found. "
                    f"Consider writing a new {note_type} first."
                )
            )
        try:
            content = read_file(path)
            if old_string not in content:
                raise Exception(
                    f"The specified string to replace was not found in the {note_type}. "(
                        f"Try reading the {note_type} to verify its content or "
                        f"write a new one if needed."
                    )
                )
            new_content = content.replace(old_string, new_string, 1)
            write_file(path, new_content)
            return json.dumps({"success": True, "path": path})
        except Exception:
            raise Exception(
                f"Failed to replace content in the {note_type}. "(
                    f"Try reading the {note_type} to verify its content or "
                    f"write a new one if needed."
                )
            )
