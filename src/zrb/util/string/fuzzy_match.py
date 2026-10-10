"""Locate a block of text in content despite whitespace or indentation drift."""


def find_fuzzy_match(content: str, old_text: str) -> str | None:
    """Try relaxed matching strategies in order. Returns the actual content substring or None."""
    for strategy in (_match_line_trimmed, _match_indentation_flexible):
        result = strategy(content, old_text)
        if result is not None:
            return result
    return None


def _match_line_trimmed(content: str, old_text: str) -> str | None:
    """Return actual content substring matching old_text after stripping trailing whitespace per line."""
    old_lines = old_text.splitlines()
    if not old_lines:
        return None
    old_stripped = [line.rstrip() for line in old_lines]
    content_lines = content.splitlines(keepends=True)
    n = len(old_lines)
    for i in range(len(content_lines) - n + 1):
        block = content_lines[i : i + n]
        if [line.rstrip() for line in block] == old_stripped:
            return "".join(block)
    return None


def _match_indentation_flexible(content: str, old_text: str) -> str | None:
    """Return actual content substring matching old_text after removing common indentation."""
    old_lines = old_text.splitlines()
    if len(old_lines) < 2:
        return None  # single-line indent shifts are too ambiguous

    def _min_indent(lines: list[str]) -> int:
        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            return 0
        return min(len(line) - len(line.lstrip()) for line in non_empty)

    old_dedented = [line[_min_indent(old_lines) :] for line in old_lines]
    content_lines = content.splitlines(keepends=True)
    n = len(old_lines)
    for i in range(len(content_lines) - n + 1):
        block = content_lines[i : i + n]
        block_clean = [line.rstrip("\n").rstrip("\r") for line in block]
        shift = _min_indent(block_clean)
        if [line[shift:] for line in block_clean] == old_dedented:
            return "".join(block)
    return None
