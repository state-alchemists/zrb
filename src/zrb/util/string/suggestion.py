"""Close-match suggestions for mistyped CLI names."""

from difflib import get_close_matches


def suggest_name(
    typo: str, candidates: list[str], limit: int = 3, cutoff: float = 0.6
) -> list[str]:
    """Return the candidates closest to `typo`, best match first.

    Args:
        typo: What the user typed.
        candidates: Names that would have been accepted.
        limit: Maximum number of suggestions to return.
        cutoff: How alike (0 to 1) a candidate must be to be suggested.

    Returns:
        Up to `limit` close matches, or an empty list when nothing is close
        enough to be worth showing.
    """
    if not typo or not candidates:
        return []
    # difflib's default 0.6 errs toward silence.
    return get_close_matches(typo, candidates, n=limit, cutoff=cutoff)


def format_suggestion(typo: str, candidates: list[str]) -> str:
    """Render a ` Did you mean ...?` clause, or `""` when nothing is close.

    The leading space lets callers append this to a message unconditionally.
    """
    matches = suggest_name(typo, candidates)
    if not matches:
        return ""
    if len(matches) == 1:
        return f" Did you mean '{matches[0]}'?"
    quoted = ", ".join(f"'{match}'" for match in matches)
    return f" Did you mean one of {quoted}?"
