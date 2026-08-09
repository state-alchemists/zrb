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
   LLM to pass it as ``cwd`` to ``Shell``. Cleared automatically when
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

import asyncio
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.prompt.profile import active_preset

# Anchors the <live-context> contract in the cached system prompt. Stable text
# — costs nothing per turn and never invalidates the cacheable prefix — while
# telling any model (not just ones that learned <system-reminder>) what the
# block is and that the most recent one wins.
# It names no individual line: a constrained preset renders no todo or worktree
# line, and an anchor that promises lines the composition cannot produce is the
# same dangle as a rulebook naming an absent tool, minus the test that catches
# it. The block is self-describing once it arrives.
_LIVE_CONTEXT_ANCHOR = (
    "Each user turn ends with a <live-context> block describing current runtime "
    "state. It is injected automatically — not written by the user. Treat the "
    "most recent <live-context> as authoritative; earlier ones are stale "
    "snapshots from when that turn was sent."
)


SimpleLiveContextProvider = Callable[[AnyContext], str | None]


def _admits(model: "Any", tool: str) -> bool:
    """Whether the active preset registers *tool* for *model*.

    Injected context is the third channel that can name a tool, after the prompt
    sections and the tool docstrings. ADR-0049 promises a preset's tool surface
    is closed under cross-reference;
    a `<live-context>` line announcing `AskUserQuestion` to a preset that never
    registered it breaks that promise from outside every test that guards it.
    """
    return active_preset(model).admits(tool)


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
    git_timeout = CFG.LLM_GIT_CMD_TIMEOUT / 1000  # knob is in milliseconds
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_git_branch = ex.submit(
            subprocess.run,
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=git_timeout,
        )
        f_git_status = ex.submit(
            subprocess.run,
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=git_timeout,
        )
        f_git_log = ex.submit(
            subprocess.run,
            ["git", "log", "--oneline", "-5"],
            capture_output=True,
            text=True,
            timeout=git_timeout,
        )
        f_todos = ex.submit(_safe_get_todos, todo_manager, session_name)

        try:
            branch = f_git_branch.result().stdout.strip() or "(detached)"
            status = f_git_status.result().stdout.strip()
            status_str = (
                "Clean" if not status else f"Dirty ({len(status.splitlines())} changes)"
            )
            git_lines.append(f"- Git: {branch} ({status_str})")
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to read git status for live context: {e}")
        try:
            recent_log = f_git_log.result().stdout.strip()
            if recent_log:
                log_lines = "\n".join(f"  {line}" for line in recent_log.splitlines())
                git_lines.append(f"- Recent commits:\n{log_lines}")
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to read git log for live context: {e}")
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
    mid-session (ADR-0042). It is injected into the conversation instead, at the
    two — and only two — moments it can otherwise be absent: the first turn
    (``render_live_context(inject_journal_index=True)``) and each summarization
    (baked into the summary by ``summarize_history``). Returns ``None`` when the
    index is missing or empty, and when ``LLM_JOURNAL_INDEX_MAX_CHARS`` is 0.

    A missing block is therefore not proof of an empty journal — and nothing
    tells the model so, since ADR-0055 leaves the journal as three tools and no
    prose. Left as a known gap rather than papered over: the only places it
    could go are the prompt (which ADR-0055 deliberately keeps empty of journal
    prose) or ``SearchJournal``'s docstring, and a
    docstring ships with its schema on *every* request, so a caveat about a
    config most deployments never touch would be paid for on every turn
    forever. It matters only when ``LLM_JOURNAL_INDEX_MAX_CHARS`` is 0 while the
    journal tools stay registered, which is a deliberate and unusual pairing.
    """
    # Callers pick the moment (first turn / summarization); this check is what
    # LLM_JOURNAL_ENABLED clears — but summarize_history reaches this directly,
    # so the switch is honoured here too rather than trusting every call path.
    if not CFG.LLM_JOURNAL_ENABLED:
        return None
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
    # A negative value disables the cap. Zero does not: "max 0 chars" reads as
    # "inject nothing", and EnvField falls back to 0 on an unparseable value —
    # so treating 0 as unlimited would let a typo'd env var silently uncap the
    # injection instead of failing loudly.
    limit = CFG.LLM_JOURNAL_INDEX_MAX_CHARS
    if limit == 0:
        return None
    hint = ""
    if limit > 0 and len(content) > limit:
        # Cut on a line boundary. A raw slice lands mid-word, so the last
        # surviving entry arrives as a fragment the model has to guess at —
        # and the HUD's entries are facts about the user, where half a
        # sentence is worse than none. Overflow is dropped from the end, so
        # the file is written most-durable-first (WriteJournalNote keeps the
        # unbounded Recent Insights section last, so overflow evicts itself).
        head = content[:limit]
        cut = head.rfind("\n")
        content = (head[:cut] if cut > 0 else head) + "\n (...more)"
        # Say where the rest is. This block is the whole of what the model is
        # handed unprompted, so without this line a cut tail is simply
        # invisible — the block reads as the complete index.
        hint = f"Truncated at `(...more)`; Read {index_file} for the rest. "
    return (
        f"<journal-index>\n"
        f"Your persistent memory (index file: {index_name}). "
        f"{hint}"
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

    The ``model`` argument resolves the active preset, so a line naming a tool
    is emitted only where that tool is registered (``_admits``). It is not
    rendered as text — the model identity line is a stable fact and lives in
    ``system_context``.

    On the async per-turn hot path, prefer ``render_live_context_async`` — this
    sync form blocks its caller for the duration of the git subprocesses.
    """
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.tool.plan import todo_manager

    session_name, interactive_bool = _wire_ambient_state(ctx)
    git_lines, todos_data = _collect_git_info(todo_manager, session_name)
    return _render_parts(
        git_lines, todos_data, interactive_bool, inject_journal_index, model
    )


async def render_live_context_async(
    ctx: AnyContext, model: "Any" = None, inject_journal_index: bool = False
) -> str:
    """``render_live_context`` for async callers (the per-turn hot path).

    The ContextVar wiring runs on the event loop (writes must land in the
    caller's context); only the git subprocesses + todo fetch are offloaded —
    inline they freeze the TUI at the start of every turn for as long as
    ``git status`` takes (routinely hundreds of ms on WSL2 / large repos).
    """
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.tool.plan import todo_manager

    session_name, interactive_bool = _wire_ambient_state(ctx)
    git_lines, todos_data = await asyncio.to_thread(
        _collect_git_info, todo_manager, session_name
    )
    return _render_parts(
        git_lines, todos_data, interactive_bool, inject_journal_index, model
    )


def _wire_ambient_state(ctx: AnyContext) -> tuple[str, bool]:
    """Per-turn ContextVar wiring (must run on the caller's thread/context).

    Returns ``(session_name, interactive_bool)``.
    """
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.tool.ambient_state import (
        set_current_tool_session,
        set_interactive_mode,
    )

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
    return session_name, interactive_bool


def _render_parts(
    git_lines: list[str],
    todos_data: "dict[str, Any] | None",
    interactive_bool: bool,
    inject_journal_index: bool,
    model: "Any" = None,
) -> str:
    """Assemble the live-context lines (ContextVar reads stay on the caller)."""
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.tool.ambient_state import get_active_worktree, set_active_worktree

    # --- Worktree (ContextVar — must run on caller's thread) ---
    active_wt = get_active_worktree()
    if active_wt and not os.path.isdir(active_wt):
        set_active_worktree("")
        active_wt = ""

    parts: list[str] = [
        f"- Time: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}",
    ]
    parts.extend(git_lines)
    if active_wt:
        parts.append(
            f"- Active worktree: {active_wt} (pass as cwd to Shell; use absolute paths for Read/Write/Edit/Grep)"
        )
    mode_line = _format_mode_line()
    if mode_line:
        parts.append(mode_line)
    if interactive_bool:
        # Named only where it exists: `minimal` drops AskUserQuestion, and
        # announcing a tool the model cannot call is worse than saying nothing.
        parts.append(
            "- Interactive: yes (AskUserQuestion is available)"
            if _admits(model, "AskUserQuestion")
            else "- Interactive: yes"
        )
    else:
        # No tool names here. AskUserQuestion, EnterPlanMode and ExitPlanMode
        # are registered only in interactive sessions (`_resolve_interactive`
        # in common_tools.py), so this branch would spend ~55 tokens per turn
        # forbidding tools that are already absent.
        parts.append(
            "- Interactive: no — do not wait on user input mid-turn; there is no "
            "user to answer or approve a plan. Present any plan inline and "
            "proceed: decide based on the conversation and continue."
        )
    if todos_data:
        try:
            parts.extend(_format_todo_lines(todos_data))
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to format todo lines for live context: {e}")

    # The index tells the model to "Use SearchJournal for full entries", so a
    # preset that dropped the journal tools must not be handed one — it would be
    # a few hundred tokens of memory with no tool to act on it. `minimal` drops
    # them by allowlist and a user preset may drop them by denylist; both are
    # the same question, which is why this asks the surface rather than the flag.
    if inject_journal_index and _admits(model, "SearchJournal"):
        journal_block = render_journal_index()
        if journal_block:
            parts.append(journal_block)

    return "\n".join(parts)
