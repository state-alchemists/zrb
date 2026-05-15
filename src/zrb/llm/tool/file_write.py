import os


def write_file(path: str, content: str, mode: str = "w") -> str:
    """
    Writes or appends content to a file. Creates the file and any missing parent directories.

    `mode="w"` (default) overwrites; `mode="a"` appends. For large content, write in chunks:
    first chunk with mode="w", subsequent chunks with mode="a".
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, mode, encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing to file {path}: {e}"
