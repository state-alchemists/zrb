"""Volatile per-turn runtime state rendered into ``<live-context>``.

``render_live_context`` produces the session-internal lines (time, git, todos,
worktree, mode, interactivity) that change every turn. It is injected into the
latest user message (wrapped by ``PromptManager.create_live_context``) rather
than the cached system prompt — this is what makes prompt caching work even
though the live state changes every turn.

``render_live_context`` also performs the per-turn auto-injections that bridge
prompt assembly to ambient runtime state:

1. **Session wiring** — reads ``ctx.input.session`` and calls
   ``set_current_tool_session()``. The resulting ``ContextVar`` is what the todo
   tools (``TodoWrite``, ``TodoRead``) read when called without an explicit
   ``session=`` argument, so they always target the active conversation.

2. **Active worktree** — if ``EnterWorktree`` was called, the path is rendered
   as ``- Active worktree: <path>`` in the live-context block and reminds the
   LLM to pass it as ``cwd`` to ``Bash``. Cleared automatically when
   ``ExitWorktree`` is called. Read via ``get_active_worktree()`` from
   ``zrb.llm.tool.ambient_state``. If the path no longer exists on disk, the
   stale value is cleared on the spot.

3. **Pending todos** — pending and in-progress todos from the current session
   are rendered into the live-context block so the LLM sees them at the start
   of every turn without needing to call ``TodoRead`` first. Completed and
   cancelled items are omitted.

4. **Interactive mode** — reads ``ctx.input.interactive`` and calls
   ``set_interactive_mode()``. The resulting ``ContextVar`` is what
   ``ask_user_question`` consults before blocking on stdin; in non-interactive
   runs the tool short-circuits with a ``[SYSTEM SUGGESTION]`` instead.
"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext

# Anchors the <live-context> contract in the cached system prompt. Stable text
# — costs nothing per turn and never invalidates the cacheable prefix — while
# telling any model (not just ones that learned <system-reminder>) what the
# block is and that the most recent one wins.
_LIVE_CONTEXT_ANCHOR = (
    "Each user turn ends with a <live-context> block describing current runtime "
    "state (time, git, todos, worktree, mode). It is injected automatically — "
    "not written by the user. Treat the most recent <live-context> as "
    "authoritative; earlier ones are stale snapshots from when that turn was "
    "sent."
)


SimpleLiveContextProvider = Callable[[AnyContext], str | None]


def _collect_git_info(
    todo_manager, session_name: str
) -> tuple[list[str], "dict[str, Any] | None"]:
    """Run git commands and todo fetch in parallel via ThreadPoolExecutor.

    Returns (git_lines, todos_data).  *todos_data* is ``None`` when outside a
    git directory and the todo call itself failed.
    """
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.util.git import is_inside_git_dir

    if not is_inside_git_dir():
        return [], _safe_get_todos(todo_manager, session_name)

    git_lines: list[str] = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_git_branch = ex.submit(
            subprocess.run,
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        f_git_status = ex.submit(
            subprocess.run,
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        f_git_log = ex.submit(
            subprocess.run,
            ["git", "log", "--oneline", "-5"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        f_todos = ex.submit(_safe_get_todos, todo_manager, session_name)

        try:
            branch = f_git_branch.result().stdout.strip() or "(detached)"
            status = f_git_status.result().stdout.strip()
            status_str = (
                "Clean" if not status else f"Dirty ({len(status.splitlines())} changes)"
            )
            git_lines.append(f"- Git: {branch} ({status_str})")
        except Exception:
            pass
        try:
            recent_log = f_git_log.result().stdout.strip()
            if recent_log:
                log_lines = "\n".join(f"  {line}" for line in recent_log.splitlines())
                git_lines.append(f"- Recent commits:\n{log_lines}")
        except Exception:
            pass
        todos_data = f_todos.result()

    return git_lines, todos_data


def _format_todo_lines(todos_data: "dict[str, Any]") -> list[str]:
    """Format pending/in-progress todos into display lines."""
    lines: list[str] = []
    active = [
        t
        for t in todos_data.get("todos", [])
        if t["status"] in ("pending", "in_progress")
    ]
    if not active:
        return lines
    total = todos_data["total"]
    done = todos_data["completed"]
    lines.append(f"- Todos ({done}/{total} done):")
    for t in active:
        mark = "[>]" if t["status"] == "in_progress" else "[ ]"
        lines.append(f"  {mark} [{t['id']}] {t['content']}")
    return lines


def _safe_get_todos(todo_manager, session_name: str):
    try:
        return todo_manager.get_todos(session_name)
    except Exception:
        return None


def _format_mode_line() -> str | None:
    """Render the agent-mode line, or None in the default mode.

    Only emits when a non-default mode (e.g. PLAN) is active, so the section is
    byte-identical to before unless plan mode is explicitly entered.
    """
    # lazy: permission is a leaf module.
    from zrb.llm.permission.state import AgentMode, get_current_agent_mode

    if get_current_agent_mode() != AgentMode.PLAN:
        return None
    return (
        "- Active mode: PLAN (read-only — edits, shell, and delegation are "
        "blocked). Investigate, then call ExitPlanMode with your plan to resume."
    )


def render_journal_index() -> str | None:
    """Read and format the journal index snapshot for context injection.

    Kept out of the cached system prompt on purpose: embedding the mutable index
    in the cached prefix invalidated it every time the agent journaled
    mid-session (ADR-0082). It is injected into the conversation instead, at the
    two — and only two — moments it can otherwise be absent: the first turn
    (``render_live_context(inject_journal_index=True)``) and each summarization
    (baked into the summary by ``summarize_history``). Returns ``None`` when the
    index is missing or empty.
    """
    journal_dir = CFG.LLM_JOURNAL_DIR
    index_name = CFG.LLM_JOURNAL_INDEX_FILE
    index_file = os.path.abspath(
        os.path.expanduser(os.path.join(journal_dir, index_name))
    )
    if not os.path.isfile(index_file):
        return None
    try:
        with open(index_file, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None
    if not content.strip():
        return None
    if len(content) > 1000:
        content = content[:1000] + " (...more)"
    return (
        f"<journal-index>\n"
        f"Your persistent memory (index file: {index_name}). "
        f"Use SearchJournal for full entries.\n"
        f"{content}\n"
        f"</journal-index>"
    )


def render_live_context(
    ctx: AnyContext, model: "Any" = None, inject_journal_index: bool = False
) -> str:
    """Render the volatile per-turn runtime state for ``<live-context>``.

    Performs the per-turn ambient-state wiring as a side effect — session
    binding (so todo tools target the active conversation), interactive-mode
    binding (consulted by ``ask_user_question``), and stale-worktree cleanup —
    then returns the dynamic lines (time, git, worktree, mode, interactivity,
    pending todos). ``PromptManager.create_live_context`` wraps the result and
    the runner appends it to the latest user turn, keeping the system prompt
    byte-stable so prompt caching survives across turns.

    When ``inject_journal_index`` is true, the journal index snapshot is appended
    so it enters history (instead of living in the cached system prompt, which it
    would invalidate on every journal write). Callers set this on the first turn
    only (empty history); summarization re-seeds the index separately, at its own
    site (``summarize_history``).

    The ``model`` argument is accepted for parity with ``system_context`` but is
    not currently rendered here (the model identity line is a stable fact).
    """
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.tool.ambient_state import (
        get_active_worktree,
        set_active_worktree,
        set_current_tool_session,
        set_interactive_mode,
    )
    from zrb.llm.tool.plan import todo_manager

    try:
        session_name = str(ctx.input.session) if hasattr(ctx, "input") else ""
    except Exception:
        session_name = ""
    session_name = session_name.strip() or "default"
    set_current_tool_session(session_name)

    try:
        interactive_bool = bool(getattr(ctx.input, "interactive", True))
    except Exception:
        interactive_bool = True
    set_interactive_mode(interactive_bool)

    # --- Dynamic: git and todos ---
    git_lines, todos_data = _collect_git_info(todo_manager, session_name)

    # --- Worktree (ContextVar — must run on caller's thread) ---
    active_wt = get_active_worktree()
    if active_wt and not os.path.isdir(active_wt):
        set_active_worktree("")
        active_wt = ""

    parts: list[str] = [
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    parts.extend(git_lines)
    if active_wt:
        parts.append(
            f"- Active worktree: {active_wt} (pass as cwd to Shell/Bash; use absolute paths for Read/Write/Edit/Grep)"
        )
    mode_line = _format_mode_line()
    if mode_line:
        parts.append(mode_line)
    if interactive_bool:
        parts.append("- Interactive: yes (AskUserQuestion is available)")
    else:
        parts.append(
            "- Interactive: no — do not call AskUserQuestion, EnterPlanMode, or "
            "ExitPlanMode, and do not wait on user input mid-turn; there is no "
            "user to answer or approve a plan. Present any plan inline and "
            "proceed: decide based on the conversation and continue."
        )
    if todos_data:
        try:
            parts.extend(_format_todo_lines(todos_data))
        except Exception:
            pass

    if inject_journal_index:
        journal_block = render_journal_index()
        if journal_block:
            parts.append(journal_block)

    return "\n".join(parts)
