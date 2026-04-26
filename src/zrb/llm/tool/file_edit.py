import os


def _match_line_trimmed(content: str, old_text: str) -> str | None:
    """Return actual content substring matching old_text after stripping trailing whitespace per line."""
    old_lines = old_text.splitlines()
    if not old_lines:
        return None
    old_stripped = [l.rstrip() for l in old_lines]
    content_lines = content.splitlines(keepends=True)
    n = len(old_lines)
    for i in range(len(content_lines) - n + 1):
        block = content_lines[i : i + n]
        if [l.rstrip() for l in block] == old_stripped:
            return "".join(block)
    return None


def _match_indentation_flexible(content: str, old_text: str) -> str | None:
    """Return actual content substring matching old_text after removing common indentation."""
    old_lines = old_text.splitlines()
    if len(old_lines) < 2:
        return None  # Single-line indent shifts are too ambiguous to fuzzy-match

    def _min_indent(lines: list[str]) -> int:
        non_empty = [l for l in lines if l.strip()]
        if not non_empty:
            return 0
        return min(len(l) - len(l.lstrip()) for l in non_empty)

    old_dedented = [l[_min_indent(old_lines) :] for l in old_lines]
    content_lines = content.splitlines(keepends=True)
    n = len(old_lines)
    for i in range(len(content_lines) - n + 1):
        block = content_lines[i : i + n]
        block_clean = [l.rstrip("\n").rstrip("\r") for l in block]
        shift = _min_indent(block_clean)
        if [l[shift:] for l in block_clean] == old_dedented:
            return "".join(block)
    return None


def _find_fuzzy_match(content: str, old_text: str) -> str | None:
    """Try relaxed matching strategies in order. Returns the actual content substring or None."""
    for strategy in (_match_line_trimmed, _match_indentation_flexible):
        result = strategy(content, old_text)
        if result is not None:
            return result
    return None


def _trunc(s: str, n: int) -> str:
    return (s[:n] + "...") if len(s) > n else s


def replace_in_file(
    path: str,
    old_text: str,
    new_text: str,
    count: int = -1,
) -> str:
    """
    Replaces text sequences within a file. Always read the file with `Read` before calling this.

    Tries exact match first, then falls back to fuzzy matching (trailing-whitespace-tolerant,
    indentation-flexible) so minor whitespace differences don't cause unnecessary failures.

    `count=-1` (default) replaces all occurrences; `count=1` replaces only the first.
    Returns an error with near-miss hints if old_text cannot be matched.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return f"Error: File not found: {path}"

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"Error: Cannot read file {path}: {e}"

    # Exact match
    actual_old = old_text if old_text in content else None
    fuzzy_note = ""

    # Fuzzy fallback
    if actual_old is None:
        matched = _find_fuzzy_match(content, old_text)
        if matched is not None:
            actual_old = matched
            fuzzy_note = " (fuzzy match: whitespace differences were normalized)"

    if actual_old is None:
        lines = content.splitlines()
        old_lines = old_text.splitlines()
        if old_lines:
            first_line = old_lines[0]
            near_matches = [
                (i + 1, line) for i, line in enumerate(lines) if first_line in line
            ]
            if near_matches:
                preview = "\n".join(
                    f"  Line {num}: {line[:120]}" for num, line in near_matches[:3]
                )
                return (
                    f"Error: '{_trunc(old_text, 80)}' not found in {path}.\n"
                    f"Similar lines found:\n{preview}\n"
                    f"[SYSTEM SUGGESTION]: old_text must match the file exactly. "
                    f"Check for trailing spaces or indentation differences. "
                    f"Use Read to copy old_text verbatim from the file content."
                )
        return (
            f"Error: '{_trunc(old_text, 80)}' not found in {path}.\n"
            f"[SYSTEM SUGGESTION]: Use Read to get the exact content and copy old_text "
            f"verbatim from below ---CONTENT---."
        )

    match_count = content.count(actual_old)
    new_content = content.replace(actual_old, new_text, count)

    if content == new_content:
        return f"No changes made to {path}"

    try:
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        return f"Error: Cannot write file {path}: {e}"

    replacements = match_count if count == -1 else min(match_count, count)
    return f"Successfully updated {path} ({replacements} replacement(s)){fuzzy_note}"
