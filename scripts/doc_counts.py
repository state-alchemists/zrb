"""Regenerate the measured counts AGENTS.md quotes.

AGENTS.md's verb rule cites how many functions the tree holds and how varied
their leading tokens are. Those numbers were written once by hand and drifted:
the file said "5,000 functions … 596 distinct leading tokens, 43% of them used
once" while the tree measured 4,466 / 488 / 39.5%. A guide whose whole thesis is
"verify against data" should not carry a number nobody re-checks, so the counts
live here and `test/architecture/test_documented_counts.py` holds AGENTS.md to
them.

    python scripts/doc_counts.py           # measured, documented, and any drift
    python scripts/doc_counts.py --check    # exit 1 on drift (what the test runs)
    python scripts/doc_counts.py --write    # rewrite the numbers in AGENTS.md

The basis is every function definition in `src/zrb`, public and private alike:
the sentence the numbers sit in says "functions", and the leading-token variety
is a property of the tree rather than of the exported surface.
"""

from __future__ import annotations

import ast
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "zrb"
AGENTS = REPO_ROOT / "AGENTS.md"
# How the failure message names this script to the reader, whatever the cwd.
SCRIPT_PATH = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()

# The sentence in AGENTS.md that carries the counts. Anchored on its wording so
# a reworded sentence fails the test that reads it rather than silently
# unchecking the numbers.
_SENTENCE = re.compile(
    r"(?P<functions>[\d,]+) functions, which currently answer to "
    r"(?P<distinct_tokens>\d+) distinct leading tokens, "
    r"(?P<once_percent>\d+(?:\.\d+)?)% of them used once"
)


def measure() -> dict[str, int | float]:
    """The counts as the tree stands: function total, token variety, once-only %."""
    verbs: Counter[str] = Counter()
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                verbs[node.name.split("_")[0]] += 1
    distinct = len(verbs)
    used_once = sum(1 for count in verbs.values() if count == 1)
    return {
        "functions": sum(verbs.values()),
        "distinct_tokens": distinct,
        "once_percent": round(100 * used_once / distinct, 1),
    }


def _as_counts(match: re.Match[str]) -> dict[str, int | float]:
    return {
        "functions": int(match.group("functions").replace(",", "")),
        "distinct_tokens": int(match.group("distinct_tokens")),
        "once_percent": float(match.group("once_percent")),
    }


def documented(text: str | None = None) -> dict[str, int | float] | None:
    """The counts AGENTS.md states, or None when the sentence is gone."""
    source = AGENTS.read_text(encoding="utf-8") if text is None else text
    match = _SENTENCE.search(source)
    return None if match is None else _as_counts(match)


def rewrite(text: str, counts: dict[str, int | float]) -> str:
    """`text` with the counts sentence restated from `counts`."""
    replacement = (
        f"{counts['functions']:,} functions, which currently answer to "
        f"{counts['distinct_tokens']} distinct leading tokens, "
        f"{counts['once_percent']}% of them used once"
    )
    return _SENTENCE.sub(replacement, text)


def _report(counts: dict[str, int | float], stated: dict[str, int | float] | None) -> int:
    """Print measured against documented; return a shell exit code."""
    print(f"measured:   {counts}")
    if stated is None:
        print(f"documented: sentence not found in {AGENTS.name}")
        return 1
    print(f"documented: {stated}")
    if stated == counts:
        print("in sync")
        return 0
    print(f"drifted. Fix with: python {SCRIPT_PATH} --write")
    return 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    counts = measure()
    stated = documented()
    if "--write" in args:
        updated = rewrite(AGENTS.read_text(encoding="utf-8"), counts)
        AGENTS.write_text(updated, encoding="utf-8")
        print(f"rewrote the counts sentence in {AGENTS.name}: {counts}")
        return 0
    return _report(counts, stated)


if __name__ == "__main__":
    raise SystemExit(main())
