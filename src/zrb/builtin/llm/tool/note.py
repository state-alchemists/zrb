import os

from zrb.config.llm_context.config import llm_context_config


def read_long_term_note() -> str:
    """
    Reads the global long-term note.
    This note is shared across all projects and conversations.

    Returns:
        The content of the long-term note.
    """
    contexts = llm_context_config.get_notes()
    return contexts.get("/", "")


def write_long_term_note(content: str) -> str:
    """
    Writes or overwrites the global long-term note for the user.

    Use to remember key user preferences, goals, or facts that apply to all future conversations (e.g., "The user prefers TypeScript," "The user's favorite color is read"). Persistent across all projects.

    Args:
        content: Information to save. Overwrites the entire note.

    Returns:
        A confirmation message.
    """
    llm_context_config.write_note(content, "/")
    return "Long term note saved"


def read_contextual_note(path: str | None = None) -> str:
    """
    Reads a contextual note for a specific path.
    If no path is provided, it defaults to the current working directory.

    Args:
        path: The file or directory path to read the note for.
              Defaults to the current working directory.

    Returns:
        The content of the contextual note.
    """
    if path is None:
        path = os.getcwd()
    abs_path = os.path.abspath(path)
    contexts = llm_context_config.get_notes(cwd=abs_path)
    return contexts.get(abs_path, "")


def write_contextual_note(content: str, path: str | None = None) -> str:
    """
    Writes or overwrites a note for a specific file or directory.

    Use to save findings, summaries, or conclusions about specific parts of the project. Available in future when working within same context.

    Args:
        content: Information to save about the path. Overwrites any existing note for this path.
        path (str, optional): Absolute file or directory path to associate the note with. Defaults to current working directory.

    Returns:
        A confirmation message.
    """
    if path is None:
        path = os.getcwd()
    llm_context_config.write_note(content, path)
    return f"Contextual note saved to {path}"
