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

    Use this to remember key user preferences, goals, or facts that should apply to all future conversations (e.g., "The user prefers TypeScript," "The user's favorite color is read"). This note is persistent across all projects.

    Args:
        content: The information to save. This will overwrite the entire note.

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

    Use this to save your findings, summaries, or conclusions about a specific part of the project. This note will be available in the future when you are working within that same context.

    Args:
        content: The information to save about the path. This overwrites any existing note for this path.
        path (str, optional): The absolute file or directory path to associate the note with. Defaults to the current working directory.

    Returns:
        A confirmation message.
    """
    if path is None:
        path = os.getcwd()
    llm_context_config.write_note(content, path)
    return f"Contextual note saved to {path}"
