"""Complexity ratchets, measured twice because the two tools disagree.

mccabe (flake8 C901) sums a nested function's branches into its *enclosing*
function's score, so a registration or factory function — a keybinding table,
a route registrar, a tool factory returning closures — scores like genuinely
tangled logic even when every nested handler is trivial on its own. radon
scores each function in its own scope and is not fooled by that shape, so
`RADON_LIMIT` is the number worth holding down.

A function inflated by that shape carries `# noqa: C901` at its `def` line
with a one-line reason, verified: it has at least one nested `def` and radon
scores it ≤ 4. `MCCABE_LIMIT` is what remains after those.

Both limits sit at the current maximum, so the next function to get worse
fails here. Raising either needs a one-line reason in the same diff.
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = str(REPO_ROOT / "src" / "zrb")

# Both numbers are pinned to the exact current maximum — no headroom, so the
# next function that gets worse fails here instead of being absorbed. Tighten
# as offenders are refactored down (see AGENTS.md's Code Style section on when
# a long function is fine vs not); raising either needs a one-line reason in
# the same diff, like the facade and constructor budgets.
#
# mccabe 19 is held by three functions: `strip_to_text_only`,
# `_execution_loop`, `_load_or_reindex`. radon 20 is held by two:
# `_execution_loop` and `LLMLimiter.to_str`. None of the five is
# closure-inflated (each scores within a point or two on both tools), so the
# next step down is real refactoring, not a `# noqa`.
MCCABE_LIMIT = 19
RADON_LIMIT = 20


def test_mccabe_complexity_ratchet():
    result = subprocess.run(
        ["flake8", SRC, "--select=C901", f"--max-complexity={MCCABE_LIMIT}"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Function(s) exceed the mccabe complexity ratchet ({MCCABE_LIMIT}). "
        "A genuine registration/factory function (nested handlers that "
        "mccabe sums into this score) gets `# noqa: C901` with a one-line "
        f"reason instead of raising this number:\n{result.stdout}"
    )


def test_radon_complexity_ratchet():
    report = json.loads(
        subprocess.run(
            ["radon", "cc", SRC, "--json"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    over = [
        (block["complexity"], f"{path}:{block['lineno']} {block['name']}")
        for path, blocks in report.items()
        if isinstance(blocks, list)
        for block in blocks
        if block["complexity"] > RADON_LIMIT
    ]
    assert not over, "Per-function complexity above the ratchet ({}):\n{}".format(
        RADON_LIMIT,
        "\n".join(
            f"  {score:3d}  {where}" for score, where in sorted(over, reverse=True)
        ),
    )
