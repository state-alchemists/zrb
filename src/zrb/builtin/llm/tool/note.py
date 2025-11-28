import os

from zrb.config.llm_context.config import llm_context_config


def read_long_term_note() -> str:
    """
    Reads the global long-term note, shared across all projects and conversations.

    Returns:
        str: The content of the long-term note.
    """
    contexts = llm_context_config.get_notes()
    return contexts.get("/", "")


def write_long_term_note(content: str) -> str:
    """
    Writes or overwrites the global long-term note.
    Use to remember key user preferences, goals, or facts relevant across all projects.

    Args:
        content (str): The information to save (overwrites entire note).

    Returns:
        str: A confirmation message.
    """
    llm_context_config.write_note(content, "/")
    return "Long term note saved"


def read_contextual_note(path: str | None = None) -> str:
    """
    Reads a contextual note for a specific file or directory.

    Args:
        path (str | None): The file or directory path. Defaults to current working directory.

    Returns:
        str: The content of the contextual note.
    """
    if path is None:
        path = os.getcwd()
    abs_path = os.path.abspath(path)
    contexts = llm_context_config.get_notes(cwd=abs_path)
    return contexts.get(abs_path, "")


def write_contextual_note(content: str, path: str | None = None) -> str:
    """
    Writes or overwrites a note for a specific file or directory.
    Use to save findings, summaries, or conclusions about a part of the project.

    Args:
        content (str): The information to save (overwrites any existing note).
        path (str | None): The file or directory path. Defaults to current working directory.

    Returns:
        str: A confirmation message.
    """
    if path is None:
        path = os.getcwd()
    llm_context_config.write_note(content, path)
    return f"Contextual note saved to {path}"
