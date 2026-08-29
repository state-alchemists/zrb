"""Complexity ratchets

Two independent measurements, because they disagree in one specific,
recurring way: mccabe (flake8's C901) sums a nested function's branches into
its *enclosing* function's score, so a registration/factory function — a
keybinding table, a route registrar, a tool factory returning closures — can
score as "complex" as genuinely tangled logic even though every nested
handler, scored on its own, is trivial (AGENTS.md's modularity note calls
this out by name: "keybinding tables, hook creators, constructors"). radon
scores each function in its own scope, so it isn't fooled by that shape —
it's the number worth actually holding down.

Confirmed cases of the mccabe/closure inflation (checked: each has ≥1 nested
`def`/`async def` inside it, and radon scores it ≤4) are marked
`# noqa: C901` at the `def` line with a one-line reason. `MCCABE_LIMIT` below
is what remains after those — a real ratchet on real per-function
complexity, not a number dominated by two outlier registration functions.
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = str(REPO_ROOT / "src" / "zrb")

# Tighten either number as offenders are refactored down (see
# AGENTS.md's Code Style section on when a long function is fine vs not).
MCCABE_LIMIT = 22
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
