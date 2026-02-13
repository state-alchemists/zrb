import os
from typing import Callable

from zrb.llm.note.manager import NoteManager
from zrb.llm.note.manager import note_manager as default_note_manager


def create_read_long_term_note_tool(
    note_manager: NoteManager | None = None,
) -> Callable:
    if note_manager is None:
        note_manager = default_note_manager

    async def read_long_term_note() -> str:
        """
        Retrieves your GLOBAL 🧠 Long-Term Memory.
        This contains established preferences, personal facts, and context spanning
        multiple projects. ALWAYS check this at the start of a session.
        """
        return note_manager.read("~")

    read_long_term_note.__name__ = "ReadLongTermNote"
    return read_long_term_note


def create_write_long_term_note_tool(
    note_manager: NoteManager | None = None,
) -> Callable:
    if note_manager is None:
        note_manager = default_note_manager

    async def write_long_term_note(content: str) -> str:
        """
        Updates your GLOBAL 🧠 Long-Term Memory with CRITICAL information.
        Use this to persist user preferences, personal facts, and cross-project rules.

        **WARNING:** This COMPLETELY OVERWRITES the existing Long-Term Note.

        **ARGS:**
        - `content`: The full text to store in the global memory.
        """
        note_manager.write("~", content)
        return "Global long-term note saved."

    write_long_term_note.__name__ = "WriteLongTermNote"
    return write_long_term_note


def create_read_contextual_note_tool(
    note_manager: NoteManager | None = None,
) -> Callable:
    if note_manager is None:
        note_manager = default_note_manager

    async def read_contextual_note(path: str | None = None) -> str:
        """
        Retrieves LOCAL 📝 Contextual Notes for a specific project or directory.
        Use this to recall architectural decisions or project-specific guidelines.

        **ARGS:**
        - `path`: Target file/dir path. Defaults to current working directory.
        """
        if path is None:
            path = os.getcwd()
        return note_manager.read(path)

    read_contextual_note.__name__ = "ReadContextualNote"
    return read_contextual_note


def create_write_contextual_note_tool(
    note_manager: NoteManager | None = None,
) -> Callable:
    if note_manager is None:
        note_manager = default_note_manager

    async def write_contextual_note(content: str, path: str | None = None) -> str:
        """
        Persists LOCAL 📝 Contextual Notes for a specific project or directory.
        Use this to save architectural patterns or progress markers for the current task.

        **WARNING:** This COMPLETELY OVERWRITES the contextual note for the specified path.

        **ARGS:**
        - `content`: The full text to store in the local memory.
        - `path`: Target file/dir path. Defaults to current working directory.
        """
        if path is None:
            path = os.getcwd()
        note_manager.write(path, content)
        return f"Contextual note saved for: {path}"

    write_contextual_note.__name__ = "WriteContextualNote"
    return write_contextual_note
