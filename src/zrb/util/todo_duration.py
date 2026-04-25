"""Duration string parsing and formatting (e.g. `1h30m` ↔ 5400 seconds)."""

from __future__ import annotations

import re

_PARSE_UNITS = {"M": 2592000, "w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_FORMAT_UNITS = [
    ("w", 604800),
    ("d", 86400),
    ("h", 3600),
    ("m", 60),
    ("s", 1),
]


def add_duration(duration1: str, duration2: str) -> str:
    """Add two duration strings and return the result in canonical form."""
    return _format_duration(parse_duration(duration1) + parse_duration(duration2))


def parse_duration(duration: str) -> int:
    """Parse a duration string like `1w2d3h` into total seconds."""
    total_seconds = 0
    for value, unit in re.findall(r"(\d+)([Mwdhms])", duration):
        total_seconds += int(value) * _PARSE_UNITS[unit]
    return total_seconds


def _format_duration(total_seconds: int) -> str:
    """Format total seconds into a compact duration string (`0s` for zero)."""
    result = []
    for unit, value_in_seconds in _FORMAT_UNITS:
        if total_seconds >= value_in_seconds:
            amount, total_seconds = divmod(total_seconds, value_in_seconds)
            result.append(f"{amount}{unit}")
    return "".join(result) if result else "0s"
