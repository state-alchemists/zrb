import os

from zrb.config.config import CFG
from zrb.util.truncate import truncate_output


def read_file(
    path: str,
    auto_truncate: bool = True,
) -> str:
    """
    Reads a file's full content. Long files are truncated to the configured
    limits (default: first/last 1000 lines, 100k chars); the header reports
    exactly what was kept.

    Output format: a metadata header line (`[File: ... | N lines]`) followed by a
    `---CONTENT---` delimiter, then the file body. When copying text for Edit's
    `old_text`, take it from below the `---CONTENT---` marker only.
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
            shown_lines = truncation_info["truncated_lines"]
            truncated = truncation_info["truncation_type"] != "none"
        else:
            shown_lines = total_lines
            truncated = False

        header = _format_read_header(
            path,
            shown_lines,
            total_lines,
            truncated,
            preserved_head_lines,
            preserved_tail_lines,
        )
        return f"{header}{content}"

    except UnicodeDecodeError:
        return (
            f"Error: File {path} appears to be binary or non-UTF-8. "
            "[SYSTEM SUGGESTION]: This tool only reads UTF-8 text. Skip this "
            "file or use a tool suited to binary content."
        )
    except Exception as e:
        return (
            f"Error reading file {path}: {e}. "
            "[SYSTEM SUGGESTION]: Verify the path and your read permissions, "
            "then retry."
        )


def _validate_path_for_reading(abs_path: str) -> str | None:
    """Validates if the path exists and is a file."""
    if not os.path.exists(abs_path):
        return (
            f"Error: File not found: {abs_path}. "
            "[SYSTEM SUGGESTION]: Check the path; use List to see what exists "
            "in the directory."
        )
    if os.path.isdir(abs_path):
        return (
            f"Error: {abs_path} is a directory. "
            "[SYSTEM SUGGESTION]: Use List to view directory contents."
        )
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
    path: str,
    shown_lines: int,
    total_lines: int,
    truncated: bool,
    head_lines: int,
    tail_lines: int,
) -> str:
    """
    Formats the header information for the read content.

    Uses a clear delimiter so the LLM can unambiguously distinguish
    metadata from file content. The content below ---CONTENT---
    is the actual file content; everything above is NOT part of the file.

    When truncation elides the middle of the file (head + tail kept), the
    shown lines are NOT a contiguous range, so the header honestly reports
    the first/last split rather than a misleading ``lines X–Y`` range.
    """
    if not truncated:
        return f"[File: {path} | {total_lines} lines]\n---CONTENT---\n"

    # Middle elided only when the file is longer than the kept head+tail window.
    middle_elided = total_lines > head_lines + tail_lines
    if middle_elided:
        meta = (
            f"[File: {path} | showing first {head_lines} and last {tail_lines} "
            f"of {total_lines} lines (middle elided) | "
            f"truncated — use Grep to locate sections, then Read again]"
        )
    else:
        meta = (
            f"[File: {path} | {shown_lines} of {total_lines} lines shown | "
            f"truncated — use Grep to locate sections, then Read again]"
        )
    return f"{meta}\n---CONTENT---\n"
