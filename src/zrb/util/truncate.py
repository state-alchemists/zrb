from collections.abc import Mapping, Sequence
from typing import Any, TypedDict


class TruncationInfo(TypedDict):
    """Information about truncation performed by truncate_output."""

    original_lines: int
    original_chars: int
    truncated_lines: int
    truncated_chars: int
    omitted_lines: int
    omitted_chars: int
    truncation_type: str  # "none", "lines", "chars", "both", "line_length"


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


def truncate_output(
    text: str,
    head_lines: int,
    tail_lines: int,
    max_line_length: int = 1000,
    max_chars: int = 100000,
) -> tuple[str, TruncationInfo]:
    """Truncates string to keep the specified number of head and tail lines.
    Returns tuple of (truncated_string, truncation_info).

    Algorithm (per requirements):
    1. If content <= max_chars, return as-is (with line length truncation if needed)
    2. Apply max_line_length truncation to all lines first
    3. If still > max_chars and line count > head_lines + tail_lines, remove lines from middle
    4. If still > max_chars, remove lines from tail (from top of tail section)
    5. If still > max_chars, remove lines from head (from bottom of head section)
    6. Insert truncation message at the point where lines were removed
    """

    lines = text.splitlines(keepends=True)
    original_lines = len(lines)
    original_chars = len(text)

    # Step 1: Apply line length truncation to all lines
    truncated_lines, line_length_truncated = _apply_line_length_truncation(
        lines, max_line_length
    )

    # Check if content already fits
    current_content = "".join(truncated_lines)
    if len(current_content) <= max_chars:
        # Content fits, return as-is
        info: TruncationInfo = {
            "original_lines": original_lines,
            "original_chars": original_chars,
            "truncated_lines": len(truncated_lines),
            "truncated_chars": len(current_content),
            "omitted_lines": 0,
            "omitted_chars": 0,
            "truncation_type": "line_length" if line_length_truncated else "none",
        }
        return current_content, info

    # Step 2: We need to truncate. Start with all lines
    kept_lines = truncated_lines[:]
    lines_removed_from_middle = 0
    lines_removed_from_tail = 0
    lines_removed_from_head = 0

    # Estimate size of truncation message (we'll add it later)
    TRUNCATION_MSG_ESTIMATE = 35

    # Step 3: If we have more lines than head+tail, remove from middle first
    kept_lines, lines_removed_from_middle = _remove_lines_from_middle(
        truncated_lines, head_lines, tail_lines
    )

    # Calculate current size including estimated truncation message
    current_content = "".join(kept_lines)
    current_size_with_msg = len(current_content)
    if (
        lines_removed_from_middle > 0
        or lines_removed_from_tail > 0
        or lines_removed_from_head > 0
    ):
        current_size_with_msg += TRUNCATION_MSG_ESTIMATE

    # Step 4: If still too large (including truncation message), remove lines from tail
    kept_lines, lines_removed_from_tail, current_size_with_msg = (
        _remove_lines_from_tail(
            kept_lines, head_lines, tail_lines, current_size_with_msg, max_chars
        )
    )

    # Step 5: If still too large, remove lines from head
    kept_lines, lines_removed_from_head, current_size_with_msg = (
        _remove_lines_from_head(
            kept_lines, head_lines, tail_lines, current_size_with_msg, max_chars
        )
    )

    # Step 6: Build final result with truncation messages
    result = _build_result_with_truncation_message(
        kept_lines,
        head_lines,
        tail_lines,
        lines_removed_from_middle,
        lines_removed_from_tail,
        lines_removed_from_head,
    )

    # Step 7: Final check - if still too large (should be rare with our algorithm),
    # we need character truncation as last resort
    character_truncation_happened = False
    chars_truncated = 0

    if len(result) > max_chars:
        result, character_truncation_happened, chars_truncated = (
            _apply_character_truncation(kept_lines, max_chars)
        )

    # Calculate metrics
    result_lines_count = result.count("\n") + (
        1 if result and not result.endswith("\n") else 0
    )

    # Determine truncation type
    truncation_type = "none"
    if character_truncation_happened:
        truncation_type = "chars"
    elif (
        lines_removed_from_middle > 0
        or lines_removed_from_tail > 0
        or lines_removed_from_head > 0
    ):
        truncation_type = "lines"
    elif line_length_truncated:
        truncation_type = "line_length"

    info = {
        "original_lines": original_lines,
        "original_chars": original_chars,
        "truncated_lines": result_lines_count,
        "truncated_chars": len(result),
        "omitted_lines": original_lines - result_lines_count,
        "omitted_chars": original_chars - len(result),
        "truncation_type": truncation_type,
    }

    return result, info


def _remove_lines_from_tail(
    kept_lines: list[str],
    head_lines: int,
    tail_lines: int,
    current_size_with_msg: int,
    max_chars: int,
) -> tuple[list[str], int, int]:
    """Remove lines from tail section (from top of tail) if content still too large.

    Returns:
        tuple: (kept_lines, lines_removed_from_tail, new_current_size_with_msg)
    """
    lines_removed_from_tail = 0
    if current_size_with_msg <= max_chars or tail_lines <= 0:
        return kept_lines, lines_removed_from_tail, current_size_with_msg

    head_section = kept_lines[:head_lines] if head_lines > 0 else []
    tail_section = kept_lines[-tail_lines:] if tail_lines > 0 else []

    while len(tail_section) > 0 and current_size_with_msg > max_chars:
        # Remove first line of tail section (closest to head)
        tail_section.pop(0)
        lines_removed_from_tail += 1

        # Update kept lines and recalculate size
        kept_lines = head_section + tail_section
        current_content = "".join(kept_lines)
        current_size_with_msg = len(current_content)
        # Add truncation message estimate if any lines were removed
        if lines_removed_from_tail > 0:
            current_size_with_msg += 35  # TRUNCATION_MSG_ESTIMATE

    return kept_lines, lines_removed_from_tail, current_size_with_msg


def _remove_lines_from_head(
    kept_lines: list[str],
    head_lines: int,
    tail_lines: int,
    current_size_with_msg: int,
    max_chars: int,
) -> tuple[list[str], int, int]:
    """Remove lines from head section (from bottom of head) if content still too large.

    Returns:
        tuple: (kept_lines, lines_removed_from_head, new_current_size_with_msg)
    """
    lines_removed_from_head = 0
    if current_size_with_msg <= max_chars or head_lines <= 0:
        return kept_lines, lines_removed_from_head, current_size_with_msg

    head_section = kept_lines[:head_lines] if head_lines > 0 else []
    tail_section = kept_lines[-tail_lines:] if tail_lines > 0 else []

    while len(head_section) > 0 and current_size_with_msg > max_chars:
        # Remove last line of head section (closest to tail)
        head_section.pop()
        lines_removed_from_head += 1

        # Update kept lines and recalculate size
        kept_lines = head_section + tail_section
        current_content = "".join(kept_lines)
        current_size_with_msg = len(current_content)
        # Add truncation message estimate if any lines were removed
        if lines_removed_from_head > 0:
            current_size_with_msg += 35  # TRUNCATION_MSG_ESTIMATE

    return kept_lines, lines_removed_from_head, current_size_with_msg


def _build_result_with_truncation_message(
    kept_lines: list[str],
    head_lines: int,
    tail_lines: int,
    lines_removed_from_middle: int,
    lines_removed_from_tail: int,
    lines_removed_from_head: int,
) -> str:
    """Build final result with truncation message inserted at correct location."""
    total_lines_removed = (
        lines_removed_from_middle + lines_removed_from_tail + lines_removed_from_head
    )

    if total_lines_removed == 0:
        return "".join(kept_lines)

    result_parts = []

    # Determine what sections we have
    has_head = head_lines > 0 and len(kept_lines) > 0
    has_tail = tail_lines > 0 and len(kept_lines) > (
        head_lines - lines_removed_from_head
    )

    # Add head section if we have one
    if has_head:
        actual_head_count = min(head_lines - lines_removed_from_head, len(kept_lines))
        result_parts.extend(kept_lines[:actual_head_count])

    # Add truncation message
    result_parts.append(f"\n...[TRUNCATED {total_lines_removed} lines]...\n\n")

    # Add tail section if we have one
    if has_tail:
        tail_start = max(head_lines - lines_removed_from_head, 0)
        result_parts.extend(kept_lines[tail_start:])

    return "".join(result_parts)


def _apply_character_truncation(
    kept_lines: list[str], max_chars: int
) -> tuple[str, bool, int]:
    """Apply character-level truncation as last resort.

    Returns:
        tuple: (result, character_truncation_happened, chars_truncated)
    """
    content_without_msg = "".join(kept_lines)

    # Estimate size of character truncation message
    CHAR_TRUNC_MSG_ESTIMATE = 30

    if max_chars < 15:
        # max_chars is too small for meaningful truncation message
        # Return minimal truncation indicator
        if max_chars >= 3:
            result = "..."
        else:
            result = "." * max_chars
        return result, True, len(content_without_msg)

    if len(content_without_msg) + CHAR_TRUNC_MSG_ESTIMATE > max_chars:
        # Even with just character truncation message, content is too large
        # We need to truncate the content itself
        chars_truncated = len(content_without_msg) + CHAR_TRUNC_MSG_ESTIMATE - max_chars
        available_for_content = max_chars - CHAR_TRUNC_MSG_ESTIMATE

        if available_for_content <= 0:
            # Can't even fit the truncation message!
            # Return just a minimal message
            if max_chars >= 10:
                result = f"\n...[TRUNCATED {len(content_without_msg)} chars]...\n\n"
                # Truncate the message itself if needed
                if len(result) > max_chars:
                    result = result[:max_chars]
            else:
                result = "..." if max_chars >= 3 else "." * max_chars
            return result, True, len(content_without_msg)
        else:
            half = available_for_content // 2
            result = (
                content_without_msg[:half]
                + f"\n...[TRUNCATED {chars_truncated} chars]...\n\n"
                + content_without_msg[-half:]
            )
            return result, True, chars_truncated
    else:
        # Content fits with character truncation message
        # This shouldn't happen if we got here, but handle it
        return content_without_msg, False, 0


def _apply_line_length_truncation(
    lines: list[str], max_line_length: int
) -> tuple[list[str], bool]:
    """Apply max_line_length truncation to all lines.

    Returns:
        tuple: (truncated_lines, line_length_truncated)
    """
    truncated_lines = [_truncate_line(line, max_line_length) for line in lines]
    line_length_truncated = any(len(line) > max_line_length for line in lines)
    return truncated_lines, line_length_truncated


def _truncate_line(line: str, max_line_length: int) -> str:
    """Truncate a single line if it exceeds max_line_length."""
    if len(line) > max_line_length:
        return line[:max_line_length] + " [LINE TRUNCATED]\n"
    return line
