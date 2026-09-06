"""Close-match suggestions for mistyped CLI names.

Used when the CLI rejects something the user typed — an unknown task name or
an unrecognized `--flag` — so the error can point at what they probably meant
instead of only saying no.
"""

from difflib import get_close_matches


def suggest_name(typo: str, candidates: list[str], limit: int = 3) -> list[str]:
    """Return the candidates closest to `typo`, best match first.

    Args:
        typo: What the user typed.
        candidates: Names that would have been accepted.
        limit: Maximum number of suggestions to return.

    Returns:
        Up to `limit` close matches, or an empty list when nothing is close
        enough to be worth showing.
    """
    if not typo or not candidates:
        return []
    # 0.6 is difflib's default and errs toward silence: a suggestion the user
    # has to squint at is worse than none.
    return get_close_matches(typo, candidates, n=limit, cutoff=0.6)


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
