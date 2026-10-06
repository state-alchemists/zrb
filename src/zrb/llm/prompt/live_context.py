"""Volatile per-turn runtime state rendered into ``<live-context>``.

Injected into the latest user message rather than the cached system prompt.
Rendering also binds the ambient session and interactive-mode ``ContextVar``s
the todo tools and ``ask_user_question`` read, and clears a stale active
worktree.
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
from zrb.llm.tool.ambient_state import (
    get_active_worktree,
    get_input_provenance,
    set_active_worktree,
    set_current_tool_session,
    set_interactive_mode,
)

# Stable text for the cached system prompt explaining the <live-context> contract.
LIVE_CONTEXT_ANCHOR = (
    "Each user turn ends with a <live-context> block describing current runtime "
    "state. It is injected automatically — not written by the user. Treat the "
    "most recent <live-context> as authoritative; earlier ones are stale "
    "snapshots from when that turn was sent."
)


SimpleLiveContextProvider = Callable[[AnyContext], str | None]

# `append_live_context` always appends the block last, after "\n\n" (or bare).
_LIVE_CONTEXT_BLOCK_RE = re.compile(
    r"\n\n(<live-context>.*</live-context>)\s*\Z", re.DOTALL
)


def append_live_context(prompt_content: Any, live_context: str) -> Any:
    """Append the ``<live-context>`` block to the end of the current user turn.

    Accepts a ``str``, a multimodal ``list`` or ``None``; a falsy
    *live_context* is a no-op. Inverse of ``split_live_context``.
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
    """Split a trailing ``<live-context>`` block off a stored user message for display.

    Returns ``(message_text, live_context_block)``; the block is ``None`` (and
    *content* unchanged) when there is none.
    """
    if not content or "<live-context>" not in content:
        return content, None
    match = _LIVE_CONTEXT_BLOCK_RE.search(content)
    if not match:
        # No leading blank line (e.g. the block was the entire prompt).
        idx = content.find("<live-context>")
        if content[idx:].rstrip().endswith("</live-context>"):
            return content[:idx].rstrip(), content[idx:].rstrip()
        return content, None
    return content[: match.start()].rstrip(), match.group(1)


def _collect_worktree_lines(timeout: float) -> list[str]:
    """Render linked worktrees from the current repository, best effort."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    entries: list[tuple[str, str]] = []
    path = branch = ""
    prunable = False
    for line in (*result.stdout.splitlines(), ""):
        if line.startswith("worktree "):
            path = line.removeprefix("worktree ")
        elif line.startswith("branch "):
            branch = line.removeprefix("branch refs/heads/")
        elif line.startswith("prunable "):
            prunable = True
        elif not line and path:
            if not prunable:
                entries.append((path, branch or "(detached)"))
            path, branch, prunable = "", "", False
    if not entries:
        return []
    current = os.path.realpath(os.getcwd())
    lines = ["- Worktrees:"]
    for path, branch in entries:
        marker = ", current" if os.path.realpath(path) == current else ""
        lines.append(f"  - {branch} @ {path}{marker}")
    return lines


def _collect_git_info(
    todo_manager, session_name: str
) -> tuple[list[str], "dict[str, Any] | None"]:
    """Run git commands and todo fetch in parallel via ThreadPoolExecutor.

    Returns (git_lines, todos_data).  *todos_data* is ``None`` when outside a
    git directory and the todo call itself failed.
    """
    # lazy: zrb internal (heavy via transitive)
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
        f_worktrees = ex.submit(_collect_worktree_lines, git_timeout)
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
        git_lines.extend(f_worktrees.result())
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


def _todo_manager():
    """The `TodoManager` singleton, resolved at render time rather than import."""
    # lazy: transitively heavy via internal — `tool/plan.py` imports pydantic
    # (~50ms on every `import zrb`).
    from zrb.llm.tool.plan import todo_manager

    return todo_manager


def _safe_get_todos(todo_manager, session_name: str):
    try:
        return todo_manager.get_todos(session_name)
    except Exception:
        return None


def _format_mode_line() -> str | None:
    """Render the agent-mode line, or None outside PLAN mode."""
    if get_current_agent_mode() != AgentMode.PLAN:
        return None
    return (
        "- Active mode: PLAN (read-only — edits, shell, and delegation are "
        "blocked). Investigate, then call ExitPlanMode with your plan to resume."
    )


def render_journal_index(first_message: str | None = None) -> str | None:
    """Read and format the journal index snapshot for context injection.

    Injected on the first turn and at each summarization, never into the
    cached system prompt (journaling would invalidate it). *first_message*
    adds an auto-search ``## Possibly Related`` section. Returns ``None`` when
    the journal is disabled, the index is missing or empty, or
    ``LLM_JOURNAL_INDEX_MAX_CHARS`` is 0.
    """
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
    # Negative disables the cap; 0 means "inject nothing", since EnvField
    # parses a typo to 0 and that must not uncap.
    limit = CFG.LLM_JOURNAL_INDEX_MAX_CHARS
    if limit == 0:
        return None
    hint = ""
    if limit > 0 and len(content) > limit:
        # Cut on a line boundary: half a fact is worse than none. Overflow
        # drops from the end, where WriteJournalNote keeps Recent Insights.
        head = content[:limit]
        cut = head.rfind("\n")
        content = (head[:cut] if cut > 0 else head) + "\n (...more)"
        hint = "Truncated at `(...more)`. "
    possibly_related = ""
    if first_message and CFG.LLM_JOURNAL_AUTO_SEARCH_ENABLED:
        possibly_related = _render_possibly_related(first_message)
    return (
        f"<journal-index>\n"
        f"Your persistent memory (index file: {index_file}). "
        f"{hint}"
        f"Use SearchJournal for full entries; a category's index.md (e.g. "
        f"technical/index.md) lists every note ever written in it, uncapped. "
        f"Change the journal only through LogActivity, WriteJournalNote, or "
        f"DeleteJournalNote — a direct file edit breaks the indexes, "
        f"backlinks, and git history they maintain. Search for these tools "
        f"if they are not visible.\n"
        f"{content}\n"
        f"{possibly_related}"
        f"</journal-index>"
    )


def _render_possibly_related(first_message: str) -> str:
    """Auto-search the opening message into a section marked unverified; ``""`` on no hits."""
    # lazy: zrb internal (heavy via transitive — zrb.llm.tool's __init__
    # imports pydantic_ai-dependent modules)
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
    """Render the per-turn runtime state for ``<live-context>``, wiring ambient state.

    *inject_journal_index* (first turn only) appends the journal index;
    *first_message* feeds its auto-search. *model* is accepted but unused.
    Async callers should use ``render_live_context_async``.
    """
    session_name, interactive_bool = _wire_ambient_state(ctx)
    git_lines, todos_data = _collect_git_info(_todo_manager(), session_name)
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
    """``render_live_context`` with git and todo fetch offloaded to a thread.

    ContextVar wiring stays on the event loop so its writes land in the
    caller's context.
    """
    session_name, interactive_bool = _wire_ambient_state(ctx)
    git_lines, todos_data = await asyncio.to_thread(
        _collect_git_info, _todo_manager(), session_name
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
    """Bind session and interactive-mode ContextVars; returns ``(session_name, interactive_bool)``."""
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
            "- Active worktree: "
            f"{active_wt} (pass as cwd to Shell; use absolute paths for "
            "Read/Write/Edit/Grep)"
        )
    provenance = get_input_provenance()
    if provenance:
        parts.append(f"- Input: user via {provenance.render()}")
        if provenance.transcription:
            parts.append(
                "  STT transcript may be inaccurate; verify names, paths, symbols, "
                "and commands before acting."
            )
    mode_line = _format_mode_line()
    if mode_line:
        parts.append(mode_line)
    if interactive_bool:
        parts.append("- Interactive: yes (AskUserQuestion is available)")
    else:
        # No tool names: the interactive-only tools are already absent here.
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

    if inject_journal_index:
        journal_block = render_journal_index(first_message)
        if journal_block:
            parts.append(journal_block)

    return "\n".join(parts)
