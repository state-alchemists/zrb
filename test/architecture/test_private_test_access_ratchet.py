"""Tests drive the public API (ADR-0034 / AGENTS.md), so private reaches don't grow.

Counts `test/` expressions reaching a private attribute through a name other
than `self` — a class reading its own state is not a coupling problem, and
`test_boundaries.py` covers that rule for production code with an AST visitor.
This regex is coarser: it cannot tell a foreign object from a helper class
defined in the same test, which is why the baseline is 5 rather than 0.

Those 5 are `test_openai_patch.py` naming pydantic-ai internals three times
(the module exists to monkey-patch exactly those), `test_format.py` touching
`_value` on its own locally-defined Holder, and `test_boundaries.py`'s
docstring spelling the pattern in prose. Prose here must say "a name other
than self" rather than spell a dotted example, or it inflates its own count.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
TEST_ROOT = REPO_ROOT / "test"

# Tighten as more accessors replace private reaches — see the module
# docstring for what the current baseline covers.
LIMIT = 5
_PRIVATE_ACCESS_PATTERN = re.compile(r"\b\w+\._[a-zA-Z]\w*")


def _non_self_private_access_count() -> int:
    return sum(
        1
        for path in TEST_ROOT.rglob("*.py")
        for m in _PRIVATE_ACCESS_PATTERN.finditer(path.read_text(encoding="utf-8"))
        if not m.group().startswith("self.")
    )


def test_private_test_access_does_not_grow():
    count = _non_self_private_access_count()
    assert (
        count <= LIMIT
    ), f"Non-self private test access grew from baseline ({LIMIT}) to {count}."
