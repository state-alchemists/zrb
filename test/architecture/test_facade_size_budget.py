"""Fitness function for facade-file growth.

Extracting a part is meant to shrink its owner's facade, and does not when
the property getters, setters and delegators pointing at the part stay
behind — logic moves out, boilerplate doesn't, and the file keeps its size.

This budget doesn't ban growth — a facade legitimately grows as its owner
gains genuine new public surface. It makes growth a conscious, reviewed
decision (bump the number here, in the same diff, with a reason) instead of
silent drift nobody notices until the file is the biggest one in the tree.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# Path relative to src/zrb -> max line count. Bump deliberately, in the same
# diff that grows the file, with a one-line reason — don't bump reflexively
# just to make the test pass.
# Ceilings that only ever go DOWN — see test_constructor_surface.py's note.
FACADE_BUDGETS = {
    "llm/ui/base/ui.py": 1200,
    # AskUserQuestion choice controls are a genuine public facade surface:
    # navigation, confirmation, and multi-select toggling are app-level actions.
    "llm/ui/default/ui.py": 668,
    "llm/task/chat/task.py": 1068,
    "llm/task/llm_task.py": 839,
    "llm/agent/subagent/manager.py": 299,
}


def test_facade_files_stay_within_their_size_budget():
    over_budget = {}
    for rel_path, budget in FACADE_BUDGETS.items():
        actual = len((SRC / rel_path).read_text(encoding="utf-8").splitlines())
        if actual > budget:
            over_budget[rel_path] = (actual, budget)
    assert not over_budget, (
        "Facade file(s) grew past their size budget — either the growth is "
        "real new surface (bump FACADE_BUDGETS here, with a reason) or it's "
        "delegator/property boilerplate that should have shrunk the facade "
        f"when its logic moved into a part: {over_budget}"
    )


# How far below its budget a file may sit before the budget is stale. A ceiling
# left high after a real shrink silently re-opens the space it was meant to
# close -- 200 lines of regrowth become free. The band is wide enough that
# ordinary edits don't trip it.
BUDGET_SLACK_RATIO = 0.05


def test_a_budget_is_lowered_when_its_file_shrinks():
    """`FACADE_BUDGETS` says these ceilings only ever go DOWN. That only holds
    if shrinking a file is followed by lowering its number, so this fails when
    a budget drifts far above what its file actually needs.
    """
    stale = {}
    for rel_path, budget in FACADE_BUDGETS.items():
        actual = len((SRC / rel_path).read_text(encoding="utf-8").splitlines())
        if actual < budget * (1 - BUDGET_SLACK_RATIO):
            stale[rel_path] = (actual, budget)
    assert not stale, (
        "Facade file(s) shrank well below their budget, which leaves the "
        "reclaimed lines free to grow back. Lower each budget to the new line "
        f"count in this diff: {stale}"
    )
