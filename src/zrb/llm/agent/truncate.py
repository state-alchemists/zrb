"""Deterministic, content-only truncation for tool results.

A global backstop applied in ``agent/common.py`` to every tool's model-facing
``content`` string. Individual tools (``file_read``, ``bash``) already cap their
own output via ``LLM_MAX_OUTPUT_CHARS``; this catches everything else (Grep,
AnalyzeCode, web fetches, MCP toolsets) that was previously uncapped.

Only the ``content`` string is touched — never a tool's structured
``return_value`` — so programmatic consumers are unaffected.
"""

from __future__ import annotations


def _human_size(num_chars: int) -> str:
    """Render a character count as a human-friendly size string."""
    if num_chars < 1024:
        return f"{num_chars} chars"
    kb = num_chars / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    return f"{kb / 1024:.1f} MB"


def truncate_tool_content(content: str, *, limit: int | None) -> tuple[str, bool]:
    """Return ``(possibly-truncated content, was_truncated)``.

    ``limit`` is the maximum number of characters in the model-facing string.
    ``None`` or ``<= 0`` disables truncation (content returned unchanged).

    When truncation happens, the head and tail are preserved (tool output is
    usually informative at both ends — the invocation/echo and the final
    error/result) and a marker describing how to re-fetch a narrower slice is
    inserted in the middle.
    """
    if not isinstance(content, str):
        return content, False
    if limit is None or limit <= 0 or len(content) <= limit:
        return content, False
    original_chars = len(content)
    total_lines = content.count("\n") + 1
    head_len = limit // 2
    tail_len = limit - head_len
    head = content[:head_len]
    tail = content[-tail_len:] if tail_len > 0 else ""
    marker = (
        f"\n\n…[truncated: {_human_size(original_chars)} total across "
        f"~{total_lines} lines, kept first {head_len} and last {tail_len} "
        "characters. Re-read a narrower slice: Read with start_line/end_line, a "
        "tighter Grep pattern, or pipe through head/tail in Bash.]…\n\n"
    )
    return head + marker + tail, True
