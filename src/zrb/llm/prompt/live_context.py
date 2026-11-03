"""Volatile per-turn runtime state rendered into ``<live-context>``.

Injected into the latest user message rather than the cached system prompt.
Rendering also binds the ambient session and interactive-mode ``ContextVar``s
the todo tools and ``ask_user_question`` read, and clears a stale active
worktree.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import escape
from typing import Any

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.ambient_state import (
    get_active_worktree,
    get_current_chat_session_id,
    get_input_provenance,
    set_active_worktree,
    set_current_tool_session,
    set_interactive_mode,
)
from zrb.llm.permission.state import AgentMode, get_current_agent_mode
from zrb.llm.prompt.memory_context import render_memory_block, render_memory_delta
from zrb.llm.util.live_context_block import split_live_context

# Stable text for the cached system prompt explaining the <live-context> contract.
LIVE_CONTEXT_ANCHOR = (
    "Each user turn ends with a <live-context> block describing current runtime "
    "state. It is injected automatically — not written by the user. Treat the "
    "most recent <live-context> as authoritative; earlier ones are stale "
    "snapshots from when that turn was sent."
)


def previous_git_baseline(message_history: "Sequence[object]") -> str | None:
    """The git baseline reconstructed from the blocks in *message_history*.

    A block may be a delta that omitted unchanged sections, so the newest one
    alone is not a baseline: diffing against it would report the omitted old
    commits as new. Scan back to the last block that had every section. The
    scan is not windowed — after a run of deltas the last complete block can
    sit arbitrarily far back, and a bounded one would silently fall past it.

    ``None`` means no complete baseline exists (a fresh repository, or the
    blocks were compacted away), and the caller renders the full state instead
    of a delta that might label old commits as new.

    Read from the history the run is actually using, never from a side cache:
    ``/rewind`` and ``/load`` replace that history, so the blocks found here
    are the ones the next turn should diff against.
    """
    return _merge_git_blocks(_recent_live_contexts(message_history))


def _recent_live_contexts(message_history: "Sequence[object]") -> list[str]:
    """Unwrapped live-context blocks, newest first."""
    blocks: list[str] = []
    for message in reversed(message_history):
        parts = getattr(message, "parts", None) or []
        for part in reversed(parts):
            block = _live_context_in(getattr(part, "content", None))
            if block:
                blocks.append(_unwrap_live_context(block))
    return blocks


def _merge_git_blocks(blocks: list[str]) -> str | None:
    """One block holding the newest known status/worktrees and every known commit."""
    status, commits, worktrees = _baseline_sections(blocks)
    # Without both a status and a commit list, this is not a baseline: a
    # partial one would label old commits as new, so the caller renders the
    # full state instead.
    if not (status and commits):
        return None
    return _render_git_baseline(status, commits, worktrees)


def _baseline_sections(
    blocks: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """(status, commits, worktrees) merged from the newest block to the oldest."""
    status: list[str] = []
    commits: list[str] = []
    worktrees: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        parsed = _git_state(_flatten(_previous_git_lines(block)))
        status = status or parsed["status"]
        worktrees = worktrees or parsed["worktrees"]
        _extend_new_commits(commits, seen, parsed["commits"])
        if status and worktrees and commits:
            break
    return status, commits, worktrees


def _extend_new_commits(commits: list[str], seen: set[str], found: list[str]) -> None:
    """Append commits not already in *seen*, preserving render order."""
    for commit in found:
        key = _commit_key(commit)
        if key in seen:
            continue
        seen.add(key)
        commits.append(commit)


def _render_git_baseline(
    status: list[str], commits: list[str], worktrees: list[str]
) -> str:
    """A block `_git_delta` can parse: status, then commits, then worktrees."""
    lines = list(status)
    if commits:
        lines.append("- Recent commits:")
        lines.extend(f"  {commit}" for commit in commits)
    if worktrees:
        lines.append("- Worktrees:")
        lines.extend(f"  {worktree}" for worktree in worktrees)
    return "\n".join(lines)


def _unwrap_live_context(block: str) -> str:
    """The block's content, without the wrapper tags the prompt carries."""
    text = block.strip()
    if text.startswith("<live-context>"):
        text = text[len("<live-context>") :]
    if text.endswith("</live-context>"):
        text = text[: -len("</live-context>")]
    return text.strip()


def _live_context_in(content: object) -> str | None:
    """The block in a string prompt, or in the trailing item of a multimodal one."""
    if isinstance(content, str):
        return split_live_context(content)[1]
    if isinstance(content, list):
        for item in reversed(content):
            if isinstance(item, str):
                block = split_live_context(item)[1]
                if block:
                    return block
    return None


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


def _commit_key(line: str) -> str:
    """The hash prefix that identifies a rendered commit line."""
    parts = line.split()
    return parts[0] if parts else ""


def _flatten(lines: list[str]) -> list[str]:
    """One entry per rendered line: git log and worktrees arrive as blocks."""
    flattened: list[str] = []
    for line in lines:
        flattened.extend(line.splitlines())
    return flattened


def _git_state(lines: list[str]) -> dict[str, list[str]]:
    """Split rendered git lines into status, commits and worktrees."""
    state: dict[str, list[str]] = {"status": [], "commits": [], "worktrees": []}
    section: str | None = None
    for line in lines:
        if line.startswith("- Git:"):
            state["status"] = [line]
            section = None
        elif line.startswith("- Recent commits"):
            section = "commits"
        elif line.startswith("- Worktrees:"):
            section = "worktrees"
        elif section and line.startswith("  "):
            state[section].append(line.strip())
        else:
            section = None
    return state


def _previous_git_lines(block: str) -> list[str]:
    """The git lines of a previous live-context block, in render order."""
    lines: list[str] = []
    active = False
    for line in block.splitlines():
        if line.startswith(("- Git:", "- Recent commits", "- Worktrees:")):
            active = True
        elif not line.startswith("  "):
            active = False
        if active:
            lines.append(line)
    return lines


def _git_delta(current: list[str], previous_block: str | None) -> list[str]:
    """What changed in git since *previous_block*, or the full state without one.

    Time always renders in full; only the git section shrinks to a delta.
    """
    if not current or previous_block is None:
        return current
    before = _git_state(_previous_git_lines(previous_block))
    now = _git_state(_flatten(current))
    if now == before:
        return ["- Git: unchanged since the last turn."]
    lines: list[str] = []
    if now["status"] != before["status"]:
        lines.extend(now["status"])
    known = {_commit_key(commit) for commit in before["commits"]}
    new_commits = [
        commit for commit in now["commits"] if _commit_key(commit) not in known
    ]
    if new_commits:
        lines.append("- Recent commits (new since the last turn):")
        lines.extend(f"  {commit}" for commit in new_commits)
    if now["worktrees"] != before["worktrees"]:
        lines.append("- Worktrees:")
        lines.extend(f"  {worktree}" for worktree in now["worktrees"])
    return lines or ["- Git: unchanged since the last turn."]


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


def _format_elapsed(seconds: float) -> str:
    """`38s`, `4m12s`, `1h02m` — short enough for one line per process."""
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    if total < 3600:
        return f"{total // 60}m{total % 60:02d}s"
    return f"{total // 3600}h{(total % 3600) // 60:02d}m"


def _background_process_lines() -> list[str]:
    """One line per background process this session still owns, if any.

    A handle is otherwise named exactly once — in the tool result that created
    it — and a later turn has only that message to go on, which compaction can
    replace. Reporting the live set here makes "there is a process running" a
    standing fact rather than a memory, which is what stops a second copy of it
    being started.

    Reads the registry without consuming it: this is a question, not the poll
    that retires a handle.
    """
    try:
        # lazy: transitively heavy via internal — the shell tool pulls
        # pydantic (~50ms on every `import zrb`).
        from zrb.llm.tool.shell_background import get_shell_background_registry

        rows = get_shell_background_registry().summary(get_current_chat_session_id())
    except (ImportError, RuntimeError) as e:
        # Unimportable here, or the registry mutated mid-read: a missing
        # section is better than a failed turn.
        CFG.LOGGER.debug(f"Failed to read background processes for live context: {e}")
        return []
    if not rows:
        return []
    lines = ["- Background processes (Shell handles this session still owns):"]
    for row in rows:
        code = row["returncode"]
        status = "running" if code is None else f"exited, code {code}"
        # The description is a command line, or whatever the caller wrote: it
        # must not be able to close this block early. `escape` leaves a normal
        # command untouched and renders `</live-context>` as text.
        description = escape(
            (row["description"] or "unnamed").replace("\n", " ")[:80], quote=False
        )
        lines.append(
            f"  - {row['handle']} ({status}, {_format_elapsed(row['seconds'])}): "
            f"{description}"
        )
    lines.append("  MonitorProcess(handle) reads one; kill=True stops it.")
    return lines


def _format_mode_line() -> str | None:
    """Render the agent-mode line, or None outside PLAN mode."""
    if get_current_agent_mode() != AgentMode.PLAN:
        return None
    return (
        "- Active mode: PLAN (read-only — edits, shell, and delegation are "
        "blocked). Investigate, then call ExitPlanMode with your plan to resume."
    )


def render_live_context(
    ctx: AnyContext,
    model: "Any" = None,
    inject_memory: bool = False,
    previous_live_context: str | None = None,
) -> str:
    """Render the per-turn runtime state for ``<live-context>``, wiring ambient state.

    *inject_memory* (first turn only) appends the memory block; every later turn
    carries only what changed since. *model* is accepted but unused. Async callers
    should use ``render_live_context_async``.
    """
    session_name, interactive_bool = _wire_ambient_state(ctx)
    git_lines, todos_data = _collect_git_info(_todo_manager(), session_name)
    return _render_parts(
        git_lines,
        todos_data,
        interactive_bool,
        inject_memory,
        previous_live_context,
    )


async def render_live_context_async(
    ctx: AnyContext,
    model: "Any" = None,
    inject_memory: bool = False,
    previous_live_context: str | None = None,
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
        inject_memory,
        previous_live_context,
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
    inject_memory: bool,
    previous_live_context: str | None = None,
) -> str:
    """Assemble the live-context lines (ContextVar reads stay on the caller)."""
    active_wt = get_active_worktree()
    if active_wt and not os.path.isdir(active_wt):
        set_active_worktree("")
        active_wt = ""

    parts: list[str] = [
        f"- Time: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}",
    ]
    parts.extend(_git_delta(git_lines, previous_live_context))
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

    parts.extend(_background_process_lines())
    parts.extend(_memory_parts(inject_memory))

    return "\n".join(parts)


def render_carried_context() -> str:
    """The block that rides along with a compacted or inherited context.

    A compaction replaces the messages that carried the block, and a sub-agent
    inherits the conversation without the turn it arrived in, so both have to be
    given it again. The memory is the only store now, so there is one answer.
    """
    return render_memory_block() or ""


def _memory_parts(inject_memory: bool) -> list[str]:
    """This turn's memory block: the whole thing on a first turn, the delta after.

    The first turn of a conversation carries the block; a later turn carries only
    what changed since it went in, so a fact recorded mid-session reaches the
    next turn instead of waiting for compaction. Off only while
    ``LLM_MEMORY_ENABLED`` is off, and then nothing is injected: there is no
    second store to fall back to.
    """
    if not CFG.LLM_MEMORY_ENABLED:
        return []
    block = render_memory_block() if inject_memory else render_memory_delta()
    return [block] if block else []
