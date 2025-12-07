import os

from zrb.config.llm_context.config import llm_context_config


def read_long_term_note() -> str:
    """
    Retrieves the GLOBAL long-term memory shared across ALL sessions and projects.

    CRITICAL: Consult this first for user preferences, facts, and cross-project context.

    Returns:
        str: The current global note content.
    """
    contexts = llm_context_config.get_notes()
    return contexts.get("/", "")


def write_long_term_note(content: str) -> str:
    """
    Persists CRITICAL facts to the GLOBAL long-term memory.

    USE EAGERLY to save:
    - User preferences (e.g., "I prefer Python", "No unit tests").
    - User information (e.g., user name, user email address).
    - Important facts (e.g., "My API key is in .env").
    - Cross-project goals.
    - Anything that will be useful for future interaction across projects.

    WARNING: This OVERWRITES the entire global note. Always read first.

    Args:
        content (str): The text to strictly memorize.

    Returns:
        str: Confirmation message.
    """
    llm_context_config.write_note(content, "/")
    return "Global long-term note saved."


def read_contextual_note(path: str | None = None) -> str:
    """
    Retrieves LOCAL memory specific to a file or directory path.

    Use to recall project-specific architecture, code summaries, or past decisions
    relevant to the current working location.

    Args:
        path (str | None): Target file/dir. Defaults to current working directory (CWD).

    Returns:
        str: The local note content for the path.
    """
    if path is None:
        path = os.getcwd()
    abs_path = os.path.abspath(path)
    contexts = llm_context_config.get_notes(cwd=abs_path)
    return contexts.get(abs_path, "")


def write_contextual_note(content: str, path: str | None = None) -> str:
    """
    Persists LOCAL facts specific to a file or directory.

    USE EAGERLY to save:
    - Architectural patterns for this project/directory.
    - Summaries of large files or directories.
    - Specific guidelines for this project.
    - Anything related to this directory that will be useful for future interaction.

    WARNING: This OVERWRITES the note for the specific path. Always read first.

    Args:
        content (str): The text to memorize for this location.
        path (str | None): Target file/dir. Defaults to CWD.

    Returns:
        str: Confirmation message.
    """
    if path is None:
        path = os.getcwd()
    llm_context_config.write_note(content, path)
    return f"Contextual note saved for: {path}"
