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
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.permission.state import AgentMode, get_current_agent_mode

# Anchors the <live-context> contract in the cached system prompt. Stable text
# — costs nothing per turn and never invalidates the cacheable prefix — while
# telling any model (not just ones that learned <system-reminder>) what the
# block is and that the most recent one wins.
# It names no individual line: the block's contents vary with the environment
# (a composition may drop the todo lines), and an anchor that promises lines the
# block cannot produce is the same dangle as a rulebook naming an absent tool,
# minus the test that catches it. The block is self-describing once it arrives.
LIVE_CONTEXT_ANCHOR = (
    "Each user turn ends with a <live-context> block describing current runtime "
    "state. It is injected automatically — not written by the user. Treat the "
    "most recent <live-context> as authoritative; earlier ones are stale "
    "snapshots from when that turn was sent."
)


SimpleLiveContextProvider = Callable[[AnyContext], str | None]

# `append_live_context` always appends the block last, as `"\n\n" + block`
# onto the existing text (or bare, when there was no prior text). Matched
# non-greedily is unnecessary since the block never nests another
# `<live-context>` — only `<journal-index>` can appear inside it.
_LIVE_CONTEXT_BLOCK_RE = re.compile(
    r"\n\n(<live-context>.*</live-context>)\s*\Z", re.DOTALL
)


def append_live_context(prompt_content: Any, live_context: str) -> Any:
    """Append the ``<live-context>`` block to the end of the current user turn.

    Handles all three ``prompt_content`` shapes produced by
    ``get_prompt_content``: ``str`` (text-only), ``list[UserContent]``
    (multimodal — a trailing text element is added, keeping the block last for
    recency), and ``None`` (empty turn — the block becomes the content). A
    falsy ``live_context`` is a no-op, so callers that pass nothing leave the
    turn untouched. Counterpart to ``split_live_context``, which strips the
    block back off for display.
    """
    if not live_context:
        return prompt_content
    if prompt_content is None:
        return live_context
    if isinstance(prompt_content, str):
        return f"{prompt_content}\n\n{live_context}"
    if isinstance(prompt_content, list):
        return [*prompt_content, live_context]
    return prompt_content


def split_live_context(content: str) -> tuple[str, str | None]:
    """Split a trailing ``<live-context>`` block off a stored user message.

    History persists the live-context block inline, appended to the same
    string the user actually typed (see module docstring) — there is no
    structural tag for it. Replaying/redisplaying history should not present
    it as if the user wrote it, so callers that render saved conversations
    (CLI replay, the web chat API) use this to separate the two before
    display.

    Returns ``(message_text, live_context_block)`` — *live_context_block* is
    ``None`` when *content* carries no live-context suffix, in which case
    *message_text* is *content* unchanged.
    """
    if not content or "<live-context>" not in content:
        return content, None
    match = _LIVE_CONTEXT_BLOCK_RE.search(content)
    if not match:
        # No leading blank line (e.g. the block was the entire prompt) —
        # a bare prefix match still isolates it correctly.
        idx = content.find("<live-context>")
        if content[idx:].rstrip().endswith("</live-context>"):
            return content[:idx].rstrip(), content[idx:].rstrip()
        return content, None
    return content[: match.start()].rstrip(), match.group(1)


def _admits(model: "Any", tool: str) -> bool:
    """Whether a standard tool may be named in live context.

    Prompt profiles no longer alter the tool surface, so all registered tools
    are available in every profile.
    """
    return True


def _collect_git_info(
    todo_manager, session_name: str
) -> tuple[list[str], "dict[str, Any] | None"]:
    """Run git commands and todo fetch in parallel via ThreadPoolExecutor.

    Returns (git_lines, todos_data).  *todos_data* is ``None`` when outside a
    git directory and the todo call itself failed.
    """
    # lazy: zrb internal (heavy via transitive) — not a cycle, verified
    # empirically.
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
    if get_current_agent_mode() != AgentMode.PLAN:
        return None
    return (
        "- Active mode: PLAN (read-only — edits, shell, and delegation are "
        "blocked). Investigate, then call ExitPlanMode with your plan to resume."
    )


def render_journal_index(first_message: str | None = None) -> str | None:
    """Read and format the journal index snapshot for context injection.

    Kept out of the cached system prompt on purpose: embedding the mutable index
    in the cached prefix invalidated it every time the agent journaled
    mid-session (ADR-0042). It is injected into the conversation instead, at the
    two — and only two — moments it can otherwise be absent: the first turn
    (``render_live_context(inject_journal_index=True)``) and each summarization
    (baked into the summary by ``summarize_history``). Returns ``None`` when the
    index is missing or empty, and when ``LLM_JOURNAL_INDEX_MAX_CHARS`` is 0.

    ``first_message`` (first-turn only — callers at later checkpoints pass
    nothing) runs one auto-search against the opening user message and, if
    anything matches, folds it into a separate, clearly-unverified
    ``## Possibly Related`` section — see ``_render_possibly_related``. Gated
    independently by ``LLM_JOURNAL_AUTO_SEARCH_ENABLED``.

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
        # Mark the cut so the block does not read as the complete index; the
        # absolute path in the header tells the model where to read the rest.
        hint = "Truncated at `(...more)`. "
    possibly_related = ""
    if first_message and CFG.LLM_JOURNAL_AUTO_SEARCH_ENABLED:
        possibly_related = _render_possibly_related(first_message)
    return (
        f"<journal-index>\n"
        f"Your persistent memory (index file: {index_file}). "
        f"{hint}"
        f"Use SearchJournal for full entries. A category's index.md (e.g. "
        f"technical/index.md) lists every note ever written in it, uncapped — "
        f"Read it directly for the full history.\n"
        f"{content}\n"
        f"{possibly_related}"
        f"</journal-index>"
    )


def _render_possibly_related(first_message: str) -> str:
    """One auto-run ``SearchJournal`` against the opening message, folded into
    a section kept visually and structurally separate from the curated HUD —
    so the model cannot mistake an unverified fuzzy hit for a vetted fact.
    Returns ``""`` on no hits (including an invalid-regex message, which
    ``search_journal`` already reports as an error rather than raising)."""
    # lazy: zrb internal (heavy via transitive — zrb.llm.tool's package
    # __init__ eagerly imports several pydantic_ai-dependent tool modules)
    from zrb.llm.tool.journal import search_journal

    result = search_journal(first_message)
    hits = result.get("results") or []
    if not hits:
        return ""
    max_hits = max(CFG.LLM_JOURNAL_AUTO_SEARCH_MAX_HITS, 0)
    lines = [
        "\n## Possibly Related (auto-matched from your message, unverified — "
        "read the full note before relying on it)\n"
    ]
    for hit in hits[:max_hits]:
        lines.append(f"- {hit['file']}:{hit['line']}: {hit['content']}")
    return "\n".join(lines) + "\n"


def render_live_context(
    ctx: AnyContext,
    model: "Any" = None,
    inject_journal_index: bool = False,
    first_message: str | None = None,
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
    site (``summarize_history``). ``first_message`` is the opening user message,
    passed through to ``render_journal_index`` for its auto-search addendum —
    meaningless past the first turn, so later callers leave it unset.

    The ``model`` argument is retained for the tool-admission seam
    (``_admits``), which currently always admits — profiles do not alter the
    tool surface. It is not rendered as text: the model identity line is a
    stable fact and lives in ``system_context``.

    On the async per-turn hot path, prefer ``render_live_context_async`` — this
    sync form blocks its caller for the duration of the git subprocesses.
    """
    # lazy: circular — zrb.llm.tool.plan imports
    # zrb.llm.agent.run.runtime_state, which loads zrb.llm.agent's package
    # __init__, which imports runner.py, which imports this module
    # (live_context.py) for append_live_context. Hoisting re-enters
    # live_context.py before its own __init__ has finished.
    from zrb.llm.tool.plan import todo_manager

    session_name, interactive_bool = _wire_ambient_state(ctx)
    git_lines, todos_data = _collect_git_info(todo_manager, session_name)
    return _render_parts(
        git_lines,
        todos_data,
        interactive_bool,
        inject_journal_index,
        model,
        first_message,
    )


async def render_live_context_async(
    ctx: AnyContext,
    model: "Any" = None,
    inject_journal_index: bool = False,
    first_message: str | None = None,
) -> str:
    """``render_live_context`` for async callers (the per-turn hot path).

    The ContextVar wiring runs on the event loop (writes must land in the
    caller's context); only the git subprocesses + todo fetch are offloaded —
    inline they freeze the TUI at the start of every turn for as long as
    ``git status`` takes (routinely hundreds of ms on WSL2 / large repos).
    """
    # lazy: circular — zrb.llm.tool.plan imports
    # zrb.llm.agent.run.runtime_state, which loads zrb.llm.agent's package
    # __init__, which imports runner.py, which imports this module
    # (live_context.py) for append_live_context. Hoisting re-enters
    # live_context.py before its own __init__ has finished.
    from zrb.llm.tool.plan import todo_manager

    session_name, interactive_bool = _wire_ambient_state(ctx)
    git_lines, todos_data = await asyncio.to_thread(
        _collect_git_info, todo_manager, session_name
    )
    return _render_parts(
        git_lines,
        todos_data,
        interactive_bool,
        inject_journal_index,
        model,
        first_message,
    )


def _wire_ambient_state(ctx: AnyContext) -> tuple[str, bool]:
    """Per-turn ContextVar wiring (must run on the caller's thread/context).

    Returns ``(session_name, interactive_bool)``.
    """
    # lazy: circular — zrb.llm.tool.ambient_state imports zrb.llm.tool.ask,
    # which imports zrb.llm.agent.run.runtime_state, which loads
    # zrb.llm.agent's package __init__, which imports runner.py, which
    # imports this module (live_context.py) for append_live_context.
    # Hoisting re-enters live_context.py before its own __init__ has
    # finished.
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
    first_message: str | None = None,
) -> str:
    """Assemble the live-context lines (ContextVar reads stay on the caller)."""
    # lazy: circular — zrb.llm.tool.ambient_state imports zrb.llm.tool.ask,
    # which imports zrb.llm.agent.run.runtime_state, which loads
    # zrb.llm.agent's package __init__, which imports runner.py, which
    # imports this module (live_context.py) for append_live_context.
    # Hoisting re-enters live_context.py before its own __init__ has
    # finished.
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
        # AskUserQuestion exists only in interactive sessions, so only this
        # branch names it. `_admits` is the retained gate — always open, since
        # profiles do not alter the tool surface.
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

    # The index tells the model to "Use SearchJournal for full entries";
    # SearchJournal is always registered, so the index is handed over whenever
    # injection is on (`_admits` is the retained gate).
    if inject_journal_index and _admits(model, "SearchJournal"):
        journal_block = render_journal_index(first_message)
        if journal_block:
            parts.append(journal_block)

    return "\n".join(parts)
