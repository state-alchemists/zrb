"""Fitness function for facade-file growth.

Extracting a part is meant to shrink its owner's facade, and does not when
the property getters, setters and delegators pointing at the part stay
behind — logic moves out, boilerplate doesn't, and the file keeps its size.

A facade legitimately grows as its owner gains genuine new public surface.
That growth is a decision, so it is not absorbed silently: every count below
is the file's exact length, and any diff that changes one says so.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# Path relative to src/zrb -> the file's exact line count. Ceilings that only
# ever go DOWN: lowering one needs nothing but the diff that earns it, and
# raising one needs an ADR saying why the surface genuinely grew — not a
# comment on the line. Pinned exactly, with no headroom, because slack
# silently absorbs the next few additions, which is the drift this file
# exists to make visible.
FACADE_BUDGETS = {
    "llm/presentation/ui/base/ui.py": 1285,
    "llm/presentation/ui/default/ui.py": 818,
    "llm/orchestration/task/chat/task.py": 1047,
    "llm/orchestration/task/llm_task.py": 806,
    "llm/orchestration/subagent/manager/manager.py": 291,
}


def test_every_facade_is_exactly_its_pinned_size():
    """A facade that moved states its new size in the same diff.

    Equality rather than a ceiling: a ceiling can only notice that a file grew
    past it, so a budget that was raised to fit the growth is invisible to it.
    """
    drifted = {}
    for rel_path, budget in FACADE_BUDGETS.items():
        actual = len((SRC / rel_path).read_text(encoding="utf-8").splitlines())
        if actual != budget:
            drifted[rel_path] = (actual, budget)
    assert not drifted, (
        "Facade file(s) no longer match their pinned size — (actual, pinned). "
        "Over the pin: the growth is either real new surface, which needs an "
        "ADR and then the new number here, or the delegators and properties "
        "that should have moved into the part its logic went to. Under it: "
        "lower the number in this same diff, so the reclaimed lines cannot "
        f"grow back for free: {drifted}"
    )
