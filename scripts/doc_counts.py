"""Measure and optionally rewrite AGENTS.md's function-count sentence.

The old sentence claimed 5,000 / 596 / 43%, while the tree measured
4,466 / 488 / 39.5%; the test keeps the documented counts synchronized.

Usage: run normally to report drift, `--check` for exit status, or `--write` to
rewrite the sentence. Counts include every function in `src/zrb`.
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
# Use a cwd-independent path in failure messages.
SCRIPT_PATH = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()

# Anchor on the wording so rephrasing fails the guarding test.
_SENTENCE = re.compile(
    r"(?P<functions>[\d,]+) functions, which currently answer to "
    r"(?P<distinct_tokens>\d+) distinct leading tokens, "
    r"(?P<once_percent>\d+(?:\.\d+)?)% of them used once"
)


def measure() -> dict[str, int | float]:
    """Return current function, token-variety, and once-only counts."""
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
    """Restate the counts sentence in `text`."""
    replacement = (
        f"{counts['functions']:,} functions, which currently answer to "
        f"{counts['distinct_tokens']} distinct leading tokens, "
        f"{counts['once_percent']}% of them used once"
    )
    return _SENTENCE.sub(replacement, text)


def _report(counts: dict[str, int | float], stated: dict[str, int | float] | None) -> int:
    """Report measured versus documented counts and return an exit code."""
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


def _write(counts: dict[str, int | float]) -> int:
    """Rewrite the counts sentence only after verifying it can be found."""
    source = AGENTS.read_text(encoding="utf-8")
    updated = rewrite(source, counts)
    if documented(updated) != counts:
        print(
            f"no counts sentence found in {AGENTS.name}, so there is nothing to "
            f"restate. Restore it, or update `_SENTENCE` in {SCRIPT_PATH} to match "
            "the wording it was changed to."
        )
        return 1
    AGENTS.write_text(updated, encoding="utf-8")
    print(f"rewrote the counts sentence in {AGENTS.name}: {counts}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    counts = measure()
    stated = documented()
    if "--write" in args:
        return _write(counts)
    return _report(counts, stated)


if __name__ == "__main__":
    raise SystemExit(main())
