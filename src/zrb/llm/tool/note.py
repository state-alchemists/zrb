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

        **OPERATIONAL MANDATE:**
        - You MUST ALWAYS check this at the start of a session.
        - Contains user preferences and cross-project facts.
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
        Updates your GLOBAL 🧠 Long-Term Memory.

        **OPERATIONAL MANDATE:**
        - You MUST ALWAYS `Read` before writing to avoid losing established context.
        - You MUST ALWAYS keep notes small, atomic, and focused on rarely-changing facts.
        - Use ONLY for cross-project user preferences or critical persona facts.
        - **WARNING:** This COMPLETELY OVERWRITES existing global memory.

        **ARGS:**
        - `content`: The high-signal text to persist.
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
        Retrieves LOCAL 📝 Contextual Notes for a project or directory.

        **OPERATIONAL MANDATE:**
        - You MUST ALWAYS check this when entering a new project directory.
        - Contains rarely-changing architectural rules and patterns.

        **ARGS:**
        - `path`: Target file/dir path (default CWD).
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
        Persists LOCAL 📝 Contextual Notes for a project or directory.

        **OPERATIONAL MANDATE:**
        - You MUST ALWAYS `Read` before writing.
        - You MUST ONLY save architectural information or rules that will rarely change.
        - You MUST NEVER save transient task progress or redundant context.
        - Keep notes small, atomic, and high-signal.
        - **WARNING:** This COMPLETELY OVERWRITES the contextual note for the path.

        **ARGS:**
        - `content`: The high-signal text to persist.
        - `path`: Target path (default CWD).
        """
        if path is None:
            path = os.getcwd()
        note_manager.write(path, content)
        return f"Contextual note saved for: {path}"

    write_contextual_note.__name__ = "WriteContextualNote"
    return write_contextual_note
