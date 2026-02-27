from collections.abc import Mapping, Sequence
from typing import Any


def truncate_output(
    text: str, head_lines: int, tail_lines: int, max_line_length: int = 1000
) -> str:
    """Truncates string to keep the specified number of head and tail lines."""

    def _safe_line(line: str) -> str:
        if len(line) > max_line_length:
            return line[:max_line_length] + " [LINE TRUNCATED]\n"
        return line

    lines = text.splitlines(keepends=True)
    if len(lines) > head_lines + tail_lines:
        omitted = len(lines) - head_lines - tail_lines
        head = [_safe_line(l) for l in lines[:head_lines]]
        tail = [_safe_line(l) for l in lines[-tail_lines:]]
        return (
            "".join(head) + f"\n...[TRUNCATED {omitted} lines]...\n\n" + "".join(tail)
        )
    return "".join([_safe_line(l) for l in lines])


def truncate_str(value: Any, limit: int):
    # If value is a string, truncate
    if isinstance(value, str):
        if len(value) > limit:
            if limit < 4:
                return value[:limit]
            return value[: limit - 4] + " ..."
    # If value is a dict, process recursively
    elif isinstance(value, Mapping):
        return {k: truncate_str(v, limit) for k, v in value.items()}
    # If value is a list or tuple, process recursively preserving type
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        t = type(value)
        return t(truncate_str(v, limit) for v in value)
    # If value is a set, process recursively preserving type
    elif isinstance(value, set):
        return {truncate_str(v, limit) for v in value}
    # Other types are returned unchanged
    return value
