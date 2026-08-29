"""Guards against test/ growing new cross-object private-attribute reaches
(ADR-0034 / AGENTS.md: tests drive the public API only).

Counts test/ expressions that reach a private attribute through some other
name than `self` (that exclusion matters: a class reading its own state
isn't a coupling problem, and `test_boundaries.py` already covers that rule
for production code). This regex is a coarser tool than `test_boundaries.py`'s
AST visitor — it can't tell a foreign object from a same-test helper class —
which is exactly why the baseline isn't zero.

Baseline 5 = three legitimate exceptions kept on purpose, one of them a
false-positive of the regex itself:
  - test_openai_patch.py names pydantic-ai internals three times: that
    module exists to monkey-patch exactly those attributes, and driving
    them through getattr indirection would only hide the coupling.
  - test_format.py touches `_value` on a Holder class it defines inside
    the same test — no foreign object involved; the regex can't tell.
  - test_boundaries.py's own docstring names the singleton `__new__`
    exception pattern using a dotted example — text, not code; the regex
    can't tell that either. (This file's docstring used to make the same
    mistake about itself — say "some other name than self" instead of a
    literal dotted example, or it inflates its own count.)
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
        for m in _PRIVATE_ACCESS_PATTERN.finditer(path.read_text())
        if not m.group().startswith("self.")
    )


def test_private_test_access_does_not_grow():
    count = _non_self_private_access_count()
    assert (
        count <= LIMIT
    ), f"Non-self private test access grew from baseline ({LIMIT}) to {count}."
