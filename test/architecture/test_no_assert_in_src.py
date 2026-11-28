"""No `assert` in `src/zrb` (review of the tree, 2026-11-28).

An `assert` is not a runtime check: `python -O` removes it, and the next line
then raises an opaque `AttributeError` where the message should have named the
task or the state. In the default build it raises a bare `AssertionError` with
no context at all.

21 of them stood in production paths when the review was written, and each is now
an explicit `if ...: raise` or a condition the type checker can narrow on. This
holds that at zero: a new `assert` in `src/` fails here rather than under
someone's `-O`.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = REPO_ROOT / "src" / "zrb"

ASSERT_LINE = re.compile(r"^\s*assert\s")


def test_src_holds_no_assert():
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{number}"
        for path in sorted(SOURCE_ROOT.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if ASSERT_LINE.match(line)
    ]
    assert offenders == [], (
        "assert disappears under `python -O`; raise an error that names the state: "
        f"{offenders}"
    )
