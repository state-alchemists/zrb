"""Capped listings of named, described items — skills and sub-agents.

A catalogue that outgrows its cap is truncated with a pointer to the matching
search tool, so the cap only saves tokens and the overflow stays reachable.
"""

from typing import Protocol, Sequence, TypeVar

# Caps on-demand search output so an empty or broad query cannot dump the
# whole catalogue; 30 keeps a full page of matches visible.
SEARCH_RESULT_LIMIT = 30


class RosterItem(Protocol):
    name: str
    description: str


T = TypeVar("T")
R = TypeVar("R", bound=RosterItem)


def cap_items(items: Sequence[T], cap: int) -> tuple[list[T], int]:
    """``(shown, hidden_count)``; a *cap* below 1 means uncapped."""
    shown = list(items) if cap < 1 else list(items[:cap])
    return shown, len(items) - len(shown)


def search_roster(items: Sequence[R], query: str) -> str | None:
    """Bullet the items whose name or description contains *query*
    (case-insensitive), capped at `SEARCH_RESULT_LIMIT`; `None` for no match."""
    needle = query.strip().lower()
    matches = [
        item
        for item in items
        if not needle
        or needle in item.name.lower()
        or needle in (item.description or "").lower()
    ]
    if not matches:
        return None
    shown, hidden = cap_items(matches, SEARCH_RESULT_LIMIT)
    lines = [f"- `{item.name}`: {item.description}" for item in shown]
    if hidden > 0:
        lines.append(f"(+{hidden} more match — refine the query)")
    return "\n".join(lines)
