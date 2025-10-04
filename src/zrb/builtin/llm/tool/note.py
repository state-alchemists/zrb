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
    Writes content to the global long-term note.
    The content of this note is intended to be read by the AI Agent in the future.
    It should contain global information/preference.

    Args:
        content: The content to write to the long-term note (overwriting the existing one).

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
    Writes a contextual note for a specific path.
    The content of this note is intended to be read by the AI Agent in the future.
    The content should contain contextual information.

    If no path is provided, it defaults to the current working directory.

    Args:
        content: The new content of the note (overwriting the existing one).
        path: The file or directory path to associate the note with.
              Defaults to the current working directory.

    Returns:
        A confirmation message indicating where the note was saved.
    """
    if path is None:
        path = os.getcwd()
    llm_context_config.write_note(content, path)
    return f"Contextual note saved to {path}"
