import os
from typing import List

from pydantic_ai import Tool

from zrb.llm.note.manager import NoteManager


def create_note_tools(note_manager: NoteManager) -> List[Tool]:
    async def read_long_term_note() -> str:
        """
        Retrieves the GLOBAL 🧠 Long Term Note.
        Use this to recall user preferences, facts, and cross-project context.
        Returns:
            str: The current global note content.
        """
        return note_manager.read("~")

    async def write_long_term_note(content: str) -> str:
        """
        Persists CRITICAL facts to the GLOBAL 🧠 Long Term Note.
        USE EAGERLY to save or update:
        - User preferences.
        - User information.
        - Important facts.
        - Cross-project goals.
        WARNING: This OVERWRITES the entire Long Term Note.
        Args:
            content (str): The text to memorize.
        Returns:
            str: Confirmation message.
        """
        note_manager.write("~", content)
        return "Global long-term note saved."

    async def read_contextual_note(path: str | None = None) -> str:
        """
        Retrieves LOCAL 📝 Contextual Note specific to a directory path.
        Use to recall project-specific architecture, or past decisions
        relevant to the current working location.
        Args:
            path (str | None): Target file/dir. Defaults to current working directory (CWD).
        Returns:
            str: The local note content for the path.
        """
        if path is None:
            path = os.getcwd()
        return note_manager.read(path)

    async def write_contextual_note(content: str, path: str | None = None) -> str:
        """
        Persists LOCAL facts specific to a directory into 📝 Contextual Note.
        USE EAGERLY to save or update:
        - Architectural patterns for this project/directory.
        - Specific guidelines for this project.
        WARNING: This OVERWRITES the entire Contextual Note for a directory.
        Args:
            content (str): The text to memorize for this location.
            path (str | None): Target file/dir. Defaults to CWD.
        Returns:
            str: Confirmation message.
        """
        if path is None:
            path = os.getcwd()
        note_manager.write(path, content)
        return f"Contextual note saved for: {path}"

    return [
        Tool(read_long_term_note, name="read_long_term_note"),
        Tool(write_long_term_note, name="write_long_term_note"),
        Tool(read_contextual_note, name="read_contextual_note"),
        Tool(write_contextual_note, name="write_contextual_note"),
    ]
