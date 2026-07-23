import os

from zrb.config.config import CFG
from zrb.llm.util.pdf import extract_pdf_text
from zrb.util.truncate import truncate_text


def read_file(
    path: str,
    start_line: int = 1,
    end_line: int = -1,
) -> str:
    """
    Reads a UTF-8 text file or extracts text from a PDF. Returns lines
    [start_line, end_line], 1-indexed and inclusive; end_line=-1 means the
    last line (so the default reads the whole file). Output beyond the size
    cap is truncated at the end with a `...[TRUNCATED]` marker — narrow the
    range or Grep to locate the part you need, then Read it.

    Output: `[File: ... ]` header, then `---CONTENT---`, then the body.
    When supplying old_text to Edit, copy only from below `---CONTENT---`.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))

    validation_error = _validate_path_for_reading(abs_path)
    if validation_error:
        return validation_error

    if _is_pdf_file(abs_path):
        return _read_pdf(path, abs_path, start_line, end_line)

    safety_error = _check_file_safety(abs_path)
    if safety_error:
        return safety_error

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        range_error = _validate_range(start_line, end_line, total_lines)
        if range_error:
            return range_error

        start = max(1, start_line)
        end = total_lines if end_line == -1 else min(end_line, total_lines)
        selected = "".join(lines[start - 1 : end])

        body, truncated = truncate_text(selected, CFG.LLM_MAX_OUTPUT_CHARS, keep="head")
        header = _format_read_header(path, start, end, total_lines, truncated)
        return f"{header}{body}"

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


def _validate_range(start_line: int, end_line: int, total_lines: int) -> str | None:
    """Validates the requested 1-indexed line range against the file length."""
    if end_line != -1 and end_line < 1:
        return (
            f"Error: end_line must be >= 1 or -1 (got {end_line}). "
            "[SYSTEM SUGGESTION]: Use -1 to read through the last line."
        )
    if end_line != -1 and start_line > end_line:
        return (
            f"Error: start_line ({start_line}) is after end_line ({end_line}). "
            "[SYSTEM SUGGESTION]: Pass start_line <= end_line."
        )
    if total_lines > 0 and start_line > total_lines:
        return (
            f"Error: start_line ({start_line}) is beyond end of file "
            f"({total_lines} lines). "
            "[SYSTEM SUGGESTION]: Read a start_line within the file."
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


def _is_pdf_file(abs_path: str) -> bool:
    return abs_path.lower().endswith(".pdf")


def _read_pdf(path: str, abs_path: str, start_line: int, end_line: int) -> str:
    full_text = extract_pdf_text(abs_path)

    if full_text is None:
        return (
            f"Error reading PDF {path}: Failed to extract text. "
            "[SYSTEM SUGGESTION]: The PDF may be corrupted, scanned/image-only, "
            "or pdfplumber may not be installed."
        )

    if not full_text.strip():
        return (
            f"Error: No extractable text found in PDF {path}. "
            "[SYSTEM SUGGESTION]: This PDF may be scanned/image-only "
            "or contain no text layer. Use a tool suited to OCR."
        )

    lines = full_text.splitlines(keepends=True)
    total_lines = len(lines)

    range_error = _validate_range(start_line, end_line, total_lines)
    if range_error:
        return range_error

    start = max(1, start_line)
    end = total_lines if end_line == -1 else min(end_line, total_lines)
    selected = "".join(lines[start - 1 : end])

    body, truncated = truncate_text(selected, CFG.LLM_MAX_OUTPUT_CHARS, keep="head")
    header = _format_read_header(path, start, end, total_lines, truncated)
    return f"{header}{body}"


def _format_read_header(
    path: str,
    start: int,
    end: int,
    total_lines: int,
    truncated: bool,
) -> str:
    """
    Formats the header above the file content.

    Uses a clear ---CONTENT--- delimiter so the LLM can unambiguously distinguish
    metadata from file content: everything below it is the file, everything above
    is NOT. Reports the exact 1-indexed line range when it is a subset of the file,
    and notes truncation so a clipped read is never mistaken for the whole range.
    """
    if start == 1 and end == total_lines:
        span = f"{total_lines} lines"
    else:
        span = f"lines {start}-{end} of {total_lines}"
    if truncated:
        span += (
            f" | truncated at {CFG.LLM_MAX_OUTPUT_CHARS} chars — "
            "narrow the range or Grep to see more"
        )
    return f"[File: {path} | {span}]\n---CONTENT---\n"
