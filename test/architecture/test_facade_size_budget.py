"""Fitness function for facade-file growth.

AGENTS.md's Part pattern expects extracting a part to shrink its owner's
facade. That didn't happen for `llm/ui/base/ui.py`: this branch split
`confirmation_state.py`, `persona_state.py`, `usage.py`, and `voice_state.py`
out of it, but `ui.py` is still the largest file in `src/zrb` — every property
getter/setter and one-line delegator for those parts still lives in the
facade class itself, so extraction moved logic out without moving the
boilerplate that points at it.

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
FACADE_BUDGETS = {
    "llm/ui/base/ui.py": 1450,
    # Phase 3 (R5): LLMChatTask's mutator API grew from 1 verb per ordered
    # collection to the full append/prepend/set/remove set — this file's own
    # docstring keeps that API on the task itself rather than delegating to a
    # part, since it is this task's own construction-time data (ADR-0035).
    # Phase 4 (R8): 5 component slots gained a real settable+typed property
    # (prompt_manager, hook_manager, llm_config, llm_limiter, markdown_theme).
    "llm/task/chat/task.py": 1150,
    # Phase 6 (R12): `llm_config` (1 property+setter) replaced by two task-
    # level hook slots (`model_getter`, `model_renderer`), each with its own
    # settable+typed property.
    "llm/task/llm_task.py": 910,
    # Phase 7 (ADR-0035): construction (create_agent, create_llm_chat_task,
    # resolve_agent_build, the tool/toolset getters) moved to the new
    # SubAgentBuilding part; this file dropped from 490 lines to roster-only.
    "llm/agent/subagent/manager.py": 310,
}


def test_facade_files_stay_within_their_size_budget():
    over_budget = {}
    for rel_path, budget in FACADE_BUDGETS.items():
        actual = len((SRC / rel_path).read_text().splitlines())
        if actual > budget:
            over_budget[rel_path] = (actual, budget)
    assert not over_budget, (
        "Facade file(s) grew past their size budget — either the growth is "
        "real new surface (bump FACADE_BUDGETS here, with a reason) or it's "
        "delegator/property boilerplate that should have shrunk the facade "
        f"when its logic moved into a part: {over_budget}"
    )
