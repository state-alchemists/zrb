import os

from zrb.llm.tool.post_write_check import format_post_write_diagnostics


async def write_file(path: str, content: str, mode: str = "w") -> str:
    """
    Writes or appends content to a file. Creates the file and any missing parent directories.

    `mode="w"` (default) overwrites; `mode="a"` appends. For large content, write in chunks:
    first chunk with mode="w", subsequent chunks with mode="a".

    After a successful write, runs an LSP diagnostic on the file when a language
    server is available. Any errors introduced by the write are appended to the
    return value as a `[LSP DIAGNOSTIC]` section — investigate and fix before
    continuing.
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
