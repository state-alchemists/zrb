import os

from zrb.llm.tool.post_write_check import format_post_write_diagnostics


async def write_file(path: str, content: str, mode: str = "w") -> str:
    """
    Writes or appends to a file, creating it and any missing parent directories.

    For large content, write in chunks: first with mode="w", subsequent with mode="a".
    On success, runs LSP/static checks — errors appear as `[DIAGNOSTIC]` in the return value.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, mode, encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"Error writing to file {path}: {e}"

    suffix = await format_post_write_diagnostics(abs_path)
    return f"Successfully wrote to {path}{suffix}"
