"""A test that reaches the tree from `__file__` must reach the tree.

Three moves in a row broke tests this way: `Path(__file__).parents[4]` was the
repository root, the file moved one directory deeper, and the constant pointed at
`test/` instead. The suite reports that as a failure with no reason — the error is
a `FileNotFoundError` on a path nobody typed — so the shape is checked here, once,
instead of three times per move.

The rule is narrow on purpose: only a `parents[N]` joined with `src` is examined,
and the join has to name a directory that exists.
"""

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).parents[2]
TESTS = REPO_ROOT / "test"

# `Path(__file__).parents[3] / "src"`, with the `.resolve()` some use and the line
# break some put between the two halves.
_REACHES_SRC = re.compile(
    r"Path\(__file__\)(?:\.resolve\(\))?\.parents\[(\d+)\][\s\S]{0,60}?\bsrc\b"
)


def test_every_test_that_reaches_src_reaches_a_real_directory():
    blind: list[str] = []
    for path in sorted(TESTS.rglob("*.py")):
        # This file writes the pattern it looks for, and would find itself.
        if path == pathlib.Path(__file__).resolve():
            continue
        source = path.read_text(encoding="utf-8")
        for match in _REACHES_SRC.finditer(source):
            depth = int(match.group(1))
            reached = path.resolve().parents[depth] / "src"
            if reached.is_dir():
                continue
            line = source[: match.start()].count("\n") + 1
            blind.append(
                f"{path.relative_to(REPO_ROOT).as_posix()}:{line} "
                f"parents[{depth}] -> {reached} does not exist"
            )

    assert blind == [], (
        "These tests compute a path from `__file__` that does not exist, which is "
        f"what a stale depth looks like after a move: {blind}"
    )
