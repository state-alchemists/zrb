import os

from zrb.llm.tool.post_write_check import format_post_write_diagnostics


async def write_file(path: str, content: str, mode: str = "w") -> str:
    """
    Writes or appends to a file, creating it and any missing parent directories.

    For large content, write in chunks: first with mode="w", subsequent with mode="a".
    On success, runs LSP/static checks — errors appear as `[DIAGNOSTIC]` in the return value.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    parent = os.path.dirname(abs_path)
    # Sampled before makedirs. Creating a directory is a change to the user's
    # tree, and a silent one reads as "the path already existed" — which is how a
    # path resolved against the wrong base lands a file where nothing reads it.
    # Reported, not refused: writing a new tree is often exactly the intent.
    created_dir = bool(parent) and not os.path.isdir(parent)
    try:
        os.makedirs(parent, exist_ok=True)
        with open(abs_path, mode, encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return (
            f"Error writing to file {path}: {e}. "
            "[SYSTEM SUGGESTION]: Check that the parent path is a directory (not a "
            "file), that you have write permission, and that there is free disk "
            "space, then retry."
        )

    dir_note = f" (created new directory {parent})" if created_dir else ""
    suffix = await format_post_write_diagnostics(abs_path)
    return f"Successfully wrote to {path}{dir_note}{suffix}"
