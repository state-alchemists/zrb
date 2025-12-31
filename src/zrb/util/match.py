import os
import re


def fuzzy_match(text: str, pattern: str) -> tuple[bool, float]:
    """
    Match text against a pattern using a fuzzy search algorithm similar to VSCode's Ctrl+P.

    The pattern is split into tokens by whitespace and path separators.
    Each token must be found in the text (in order).

    Args:
        text: The string to search in.
        pattern: The search pattern (e.g., "src main" or "util/io").

    Returns:
        A tuple (matched, score).
        - matched: True if the pattern matches the text.
        - score: A float representing the match quality (lower is better).
    """
    text_cmp = text.lower()
    # Normalize pattern -> tokens split on path separators or whitespace
    search_pattern = pattern.strip()
    tokens = (
        [t for t in re.split(rf"[{re.escape(os.path.sep)}\s]+", search_pattern) if t]
        if search_pattern
        else []
    )
    tokens = [t.lower() for t in tokens]
    if not tokens:
        return True, 0.0
    last_pos = 0
    score = 0.0
    for token in tokens:
        # try contiguous substring search first
        idx = text_cmp.find(token, last_pos)
        if idx != -1:
            # good match: reward contiguous early matches
            score += idx  # smaller idx preferred
            last_pos = idx + len(token)
        else:
            # fallback to subsequence matching
            pos = _find_subsequence_pos(text_cmp, token, last_pos)
            if pos is None:
                return False, 0.0

            # subsequence match is less preferred than contiguous substring
            score += pos + 0.5 * len(token)
            last_pos = pos + len(token)
    # prefer shorter texts when score ties, so include length as tiebreaker
    score += 0.01 * len(text)
    return True, score


def _find_subsequence_pos(hay: str, needle: str, start: int = 0) -> int | None:
    """
    Try to locate needle in hay as a subsequence starting at `start`.
    Returns the index of the first matched character of the subsequence or None if not match.
    """
    if not needle:
        return start
    i = start
    j = 0
    first_pos = None
    while i < len(hay) and j < len(needle):
        if hay[i] == needle[j]:
            if first_pos is None:
                first_pos = i
            j += 1
        i += 1
    return first_pos if j == len(needle) else None
