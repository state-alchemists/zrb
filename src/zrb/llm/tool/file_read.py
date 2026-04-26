import os

from zrb.config.config import CFG
from zrb.util.truncate import truncate_output


def _validate_path_for_reading(abs_path: str) -> str | None:
    """Validates if the path exists and is a file."""
    if not os.path.exists(abs_path):
        return f"Error: File not found: {abs_path}"
    if os.path.isdir(abs_path):
        return f"Error: {abs_path} is a directory."
    return None


def _check_file_safety(abs_path: str) -> str | None:
    """Checks if the file is safe to read (size and content type)."""
    file_size = os.path.getsize(abs_path)
    if file_size > 10 * 1024 * 1024:
        return (
            f"Error: File is too large ({file_size} bytes). "
            f"[SYSTEM SUGGESTION]: Use Grep to search for specific content instead."
        )

    try:
        with open(abs_path, "rb") as f:
            chunk = f.read(1024)
            if b"\0" in chunk:
                return (
                    "Error: File appears to be binary. "
                    "Reading binary files is not supported."
                )
    except Exception:
        pass
    return None


def _format_read_header(
    path: str, start_idx: int, end_idx: int, total_lines: int, truncated: bool
) -> str:
    """
    Formats the header information for the read content.

    Uses a clear delimiter so the LLM can unambiguously distinguish
    metadata from file content. The content below ---CONTENT---
    is the actual file content; everything above is NOT part of the file.
    """
    if truncated:
        meta = (
            f"[File: {path} | lines {start_idx + 1}–{end_idx} of {total_lines} shown | "
            f"truncated — use Grep to locate sections, then Read again]"
        )
    else:
        meta = f"[File: {path} | {total_lines} lines]"
    return f"{meta}\n---CONTENT---\n"


def read_file(
    path: str,
    auto_truncate: bool = True,
) -> str:
    """
    Reads a file's full content. Truncates at 1000 head/tail lines or 100k chars.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))

    validation_error = _validate_path_for_reading(abs_path)
    if validation_error:
        return validation_error

    safety_error = _check_file_safety(abs_path)
    if safety_error:
        return safety_error

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        total_lines = content.count("\n") + 1
        max_chars = CFG.LLM_MAX_OUTPUT_CHARS
        preserved_head_lines = CFG.LLM_FILE_READ_LINES
        preserved_tail_lines = CFG.LLM_FILE_READ_LINES

        if auto_truncate:
            content, truncation_info = truncate_output(
                content,
                preserved_head_lines,
                preserved_tail_lines,
                CFG.LLM_FILE_READ_LINES,
                max_chars,
            )
            start_idx = 0
            end_idx = truncation_info["truncated_lines"]
            truncated = truncation_info["truncation_type"] != "none"
        else:
            start_idx = 0
            end_idx = total_lines
            truncated = False

        header = _format_read_header(path, start_idx, end_idx, total_lines, truncated)
        return f"{header}{content}"

    except UnicodeDecodeError:
        return f"Error: File {path} appears to be binary or non-UTF-8."
    except Exception as e:
        return f"Error reading file {path}: {e}"


def read_files(
    paths: list[str],
    auto_truncate: bool = True,
) -> dict[str, str]:
    """
    Reads multiple files in a single call. Same truncation as `Read`.

    Individual file errors don't stop batch processing.
    """
    results = {}
    for path in paths:
        results[path] = read_file(path, auto_truncate=auto_truncate)
    return results
