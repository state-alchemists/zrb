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
    # +11 (1200->1211): `set_status_badge` and `status_badges`, the status-bar
    # badge `AnyUI` declares (ADR-0102) -- new surface, not a delegator.
    # +9 (1211->1220): `is_prompt_answered_since`, beside `pending_answer_since`,
    # so speech can tell a prompt answered between two checks -- new surface.
    # +12 (1220->1232): `cancel_current_turn`, the turn cancel `AnyUI` now
    # declares so Esc and a spoken barge-in stop a turn the same way -- new
    # surface.
    # +15 (1232->1247): `execute_hook` takes the hook manager to dispatch
    # through, and `cancel_current_turn` picks the one the turn ran with (a
    # chat task's active manager, else the task's own) -- new surface.
    # +12 (1247->1259): `is_turn_running`, which `AnyUI` now declares, and a
    # `cancel_current_turn` that hands a child's cancel to its `MultiUI`
    # parent, so Esc stops the turn the parent runs -- new surface.
    # +12 (1259->1271): optional input provenance on UI submissions, so
    # integrations can identify Telegram/dictation/web turns in live context.
    # +29 (1271->1300): `remove_echo`, the delete-side `AnyUI` echo hook, and
    # `delete_queued_message` -- new surface (Ctrl+X) -- plus the module-level
    # `_broadcast_echo`, the best-effort child broadcast both it and
    # `edit_queued_message` now share instead of each carrying its own.
    # +42 (1300->1342): runtime timers for the status bar -- the `RunningTool`
    # value type, `session_started_at`/`running_tool` accessors, and the
    # `start_tool_call`/`end_tool_call` lifecycle hooks the agent stream wires
    # to -- new surface (feature 3).
    # +14 (1342->1356): `RunningTool` gains `tool_call_id` and the two
    # lifecycle hooks take the id, so a concurrent call's result event clears
    # only its own timer -- the PR #564 review fix (no new method surface).
    # +4 (1356->1360): the single `_running_tool` slot becomes a mapping keyed
    # by tool_call_id, so a newer call finishing first can't clear an older
    # still-running sibling -- the PR #564 round-2 review fix (no new method
    # surface).
    # +10 (1360->1370): `record_submitted_message`, the hook `submit_user_message`
    # calls so a UI with cross-session recall records every submitted message
    # (PR #562 round-2: keyboard, initial, and programmatic submissions) -- new
    # surface, not a delegator.
    "llm/ui/base/ui.py": 1370,
    # +11 (653->664): markdown-merge echo entry points — `render_markdown`
    # (now width-aware, for re-render on resize) and `set_rendered_block`,
    # which registers a redrawn echo as a re-renderable block. +7 (664->671):
    # `is_application_built` predicate and the hoisted `_application`
    # init it reads during UIOutput construction.
    # +10 (671->681): `remove_echo`, the delete-side counterpart to the
    # `redraw_echo` override already here -- new surface.
    # +16 (681->697): `replay_history` override seeds the input box's
    # previous-message history from a loaded conversation, and the
    # `PreviousMessageHistory` part is constructed in __init__ -- new surface.
    # +7 (697->704): `record_submitted_message` override appends to the input
    # box's `PreviousMessageHistory` (PR #562 round-2) -- new surface.
    # +4 (704->708): `reset_previous_recall`, the delegator the Enter keybinding
    # calls after a submit or a command so a submitted recall does not leave the
    # input unable to start a fresh Up-arrow recall (PR #562 round-3) -- new
    # surface, not a delegator-only line.
    "llm/ui/default/ui.py": 708,
    # +10 (1068->1078): the `stream_observers` collection (append/prepend/
    # set/remove plus its property), the seam speech streams through --
    # new surface.
    "llm/task/chat/task.py": 1078,
    # +26 (783->809): `stream_observers` with `set_stream_observers` and append/prepend/
    # remove, handed to `run_agent` -- new surface.
    # +4 (809->813): the `dynamic_yolo` docstring names the arguments a
    # per-call callable is handed, which an `arg_pattern` rule needs to be
    # judged at all -- documented contract, no new surface.
    # +7 (813->820): `/compress` publishes the session's model overrides before
    # the summarizer resolves a model. A run only publishes them once it starts,
    # and this command is handled before that -- new behavior, and the reason
    # `/model small` was being ignored.
    "llm/task/llm_task.py": 820,
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
