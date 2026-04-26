import os


def write_file(path: str, content: str, mode: str = "w") -> str:
    """
    Writes or appends content to a file. Creates the file and any missing parent directories.

    `mode="w"` (default) overwrites; `mode="a"` appends. For large content, write in chunks:
    first chunk with mode="w", subsequent chunks with mode="a".
    For existing files, read with `Read` first to avoid unintentional overwrites.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, mode, encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing to file {path}: {e}"


def write_files(files: list[dict[str, str]]) -> dict[str, str]:
    """
    Batch writes multiple files in a single call.

    Each entry must be a dict with `path` (str), `content` (str), and optional `mode` ("w"/"a").
    Creates parent directories automatically. Same chunking guidance as `Write`.
    """
    results = {}
    for file_info in files:
        path = file_info.get("path")
        content = file_info.get("content")
        mode = file_info.get("mode", "w")
        if not path or content is None:
            results[str(path)] = "Error: Missing path or content"
            continue
        results[path] = write_file(path, content, mode)
    return results
