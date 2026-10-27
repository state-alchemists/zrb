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
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
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
from zrb.llm.journal_index_name import resolve_journal_index_name
from zrb.llm.journal_usage_log import record_injected
from zrb.llm.permission.state import AgentMode, get_current_agent_mode

# Stable text for the cached system prompt explaining the <live-context> contract.
LIVE_CONTEXT_ANCHOR = (
    "Each user turn ends with a <live-context> block describing current runtime "
    "state. It is injected automatically — not written by the user. Treat the "
    "most recent <live-context> as authoritative; earlier ones are stale "
    "snapshots from when that turn was sent."
)

# `append_live_context` always appends the block last, after "\n\n" (or bare).
_LIVE_CONTEXT_BLOCK_RE = re.compile(
    r"\n\n(<live-context>.*</live-context>)\s*\Z", re.DOTALL
)

# A journal index entry: `[title](category/note.md)`.
_INDEX_LINK = re.compile(r"\[([^\]]+)\]\(([a-z0-9_-]+)/[^)]*\)")

# The trailing link of a HUD line: `- text ([note](category/slug.md))`.
_HUD_NOTE_LINK = re.compile(r"\(\[note\]\(([^)]*)\)\)[ \t]*$", re.MULTILINE)


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


def render_journal_index(first_message: str | None = None) -> str | None:
    """Read and format the journal index snapshot for context injection.

    The index is ``LLM_JOURNAL_INDEX_FILE`` under ``LLM_JOURNAL_DIR`` — the same
    knob the writers name the root and category indexes with. Injected on the
    first turn and at each summarization, never into the cached system prompt
    (journaling would invalidate it). *first_message* adds an auto-search
    ``## Possibly Related`` section. Returns ``None`` when the journal is
    disabled, the index is missing or empty, ``LLM_JOURNAL_INDEX_MAX_CHARS`` is
    0, or ``LLM_JOURNAL_INDEX_FILE`` is not a bare filename — the same check
    the writers apply, so this can never be pointed outside the journal.
    """
    if not CFG.LLM_JOURNAL_ENABLED:
        return None
    journal_dir = CFG.LLM_JOURNAL_DIR
    try:
        index_name = resolve_journal_index_name(CFG.LLM_JOURNAL_INDEX_FILE)
    except ValueError:
        return None
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
        # drops from the end, so the summary says which categories were lost
        # and names the newest note in each — otherwise the model cannot tell
        # whether the missing part matters.
        head = content[:limit]
        cut = head.rfind("\n")
        kept = head[:cut] if cut > 0 else head
        content = kept + "\n" + _overflow_summary(content[len(kept) :])
        hint = "Truncated at `(...more)`. "
    possibly_related = ""
    if first_message and CFG.LLM_JOURNAL_AUTO_SEARCH_ENABLED:
        possibly_related = _render_possibly_related(first_message)
    block = (
        f"<journal-index>\n"
        f"Your persistent memory (index file: {index_file}). "
        f"{hint}"
        f"Use SearchJournal for full entries; a category's {index_name} (e.g. "
        f"technical/{index_name}) lists every note ever written in it, uncapped. "
        f"Change the journal only through LogActivity, WriteJournalNote, or "
        f"DeleteJournalNote — and retire a note that stopped applying with "
        f"SupersedeJournalNote rather than deleting its evidence — a direct "
        f"file edit breaks the indexes, "
        f"backlinks, and git history they maintain. Search for these tools "
        f"if they are not visible.\n"
        f"{content}\n"
        f"{possibly_related}"
        f"</journal-index>"
    )
    record_injected(len(block.encode("utf-8")), _hud_note_paths(content), bool(hint))
    return block


def _hud_note_paths(content: str) -> list[str]:
    """The note path each injected HUD line links to (`([note](path))`)."""
    return [m.group(1) for m in _HUD_NOTE_LINK.finditer(content)]


def _overflow_summary(dropped: str) -> str:
    """One line per note category the cap hid, plus the newest title in it."""
    counts: dict[str, int] = {}
    newest: dict[str, str] = {}
    for line in dropped.splitlines():
        seen_here: set[str] = set()
        for title, category in _INDEX_LINK.findall(line):
            if category in seen_here:
                continue
            seen_here.add(category)
            counts[category] = counts.get(category, 0) + 1
            # The index lists newest first, so the first line seen is the newest.
            newest.setdefault(
                category, title if title != "note" else _title_before_link(line)
            )
    if not counts:
        return "(...more)"
    lines = []
    for category in sorted(counts):
        detail = f'; newest "{newest[category]}"' if newest.get(category) else ""
        lines.append(
            f"- Hidden {category} notes ({counts[category]}{detail}) — "
            "use SearchJournal."
        )
    lines.append("(...more)")
    return "\n".join(lines)


def _title_before_link(line: str) -> str:
    """The entry text before a `([note](...))` link, which is its title."""
    return line.split(" ([note]", 1)[0].lstrip("- ").strip()


def _render_possibly_related(first_message: str) -> str:
    """Auto-search the opening message into a section marked unverified; ``""`` on no hits."""
    # lazy: zrb internal (heavy via transitive — zrb.llm.tool's __init__
    # imports pydantic_ai-dependent modules)
    from zrb.llm.tool.journal import find_in_journal

    result = find_in_journal(first_message)
    found = result.get("results")
    hits = found if isinstance(found, list) else []
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


DAY_LINE_COUNT = 5
"""Most lines today contributes to the injected day block."""

YESTERDAY_LINE_COUNT = 2
"""Most lines yesterday contributes: enough to recognise the seam, not a summary."""

DAY_BLOCK_MAX_CHARS = 1500
"""Cap on the whole day block, in characters."""

_HANDOVER_HEADING = "## handover"
_IMPORTANCE = re.compile(r"·\s*imp\s*(\d+)", re.IGNORECASE)
_RANKING = re.compile(r"\s*·\s*imp\s*\d+(\s*\.)?", re.IGNORECASE)


def _without_importance(entry: str) -> str:
    """*entry* without its `· imp N` key, which orders lines rather than saying anything."""
    return _RANKING.sub("", entry).strip()


def _day_file(day: date) -> str:
    """The activity log's file for *day*, which is the day tier."""
    # lazy: `zrb.llm.tool`'s package __init__ loads pydantic_ai-dependent modules
    from zrb.llm.tool.journal_index import ACTIVITY_DIR

    root = os.path.abspath(os.path.expanduser(CFG.LLM_JOURNAL_DIR))
    return os.path.join(
        root,
        ACTIVITY_DIR,
        day.strftime("%Y"),
        day.strftime("%Y-%m"),
        f"{day.isoformat()}.md",
    )


def _read_day(path: str) -> str:
    """The day file's text, or ``""`` when it does not exist yet."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _day_entries(text: str) -> list[str]:
    """The bullet entries above the first `## ` heading, one string each.

    A plain continuation line belongs to the entry above it, which is how a wrapped
    event reads back as one line.
    """
    entries: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            break
        if line.startswith("- "):
            entries.append(line[2:].strip())
        elif line.strip() and entries:
            entries[-1] = f"{entries[-1]} {line.strip()}"
    return entries


def _importance(entry: str) -> int:
    """The `· imp N` a day line carries, or 0 when it carries none."""
    found = _IMPORTANCE.search(entry)
    return int(found.group(1)) if found else 0


def _handover(text: str) -> str:
    """The `## Handover` section without its heading, or ``""`` when absent."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().lower().startswith(_HANDOVER_HEADING):
            start = index + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body).strip()


def _top_entries(entries: list[str], count: int) -> list[str]:
    """The *count* entries that matter most, returned in the order they were written."""
    ranked = sorted(
        enumerate(entries),
        key=lambda pair: (_importance(pair[1]), pair[0]),
        reverse=True,
    )
    return [entries[index] for index in sorted(pair[0] for pair in ranked[:count])]


_DAY_BLOCK_OPEN = (
    "<day>\n"
    "Your memory of the last day or two, not a briefing: use a detail from it "
    "where it fits, and never announce or recite this block.\n\n"
)
"""The wrapper the block is sent in, with the line that says how to read it.

`render_day_block` always returns one thing. The instruction lives in the wrapper
rather than the prompt so it is paid for only when there is a block to read, and
so it travels with the text it describes."""

_DAY_BLOCK_CLOSE = "\n</day>"
_SECTION_SEPARATOR = "\n\n"
_CUT_MARKER = "…"


def _wrap_sections(sections: list[str]) -> str:
    """The `<day>` block around *sections*, each separated by a blank line."""
    return _DAY_BLOCK_OPEN + _SECTION_SEPARATOR.join(sections) + _DAY_BLOCK_CLOSE


def _room_for_next(kept: list[str]) -> int:
    """How many characters one more section may take, wrapper and separator included."""
    used = len(_wrap_sections(kept)) + (len(_SECTION_SEPARATOR) if kept else 0)
    return DAY_BLOCK_MAX_CHARS - used


def _cut_section(section: str, room: int) -> str:
    """*section* cut to at most *room* characters, on a line break when one keeps most of it."""
    if len(section) <= room:
        return section
    head = section[:room]
    line_end = head.rfind("\n")
    if line_end >= room // 2:
        return head[:line_end]
    return head[: max(0, room - len(_CUT_MARKER))].rstrip() + _CUT_MARKER


def _room_for_first_line(section: str) -> int:
    """Characters *section* needs to show its heading and one line of content."""
    heading, _, body = section.partition(_SECTION_SEPARATOR)
    first_line = body.split("\n", 1)[0]
    return len(heading) + len(_SECTION_SEPARATOR) + len(first_line)


def _reserve_for_later(sections: list[str]) -> int:
    """Room every section after the current one must keep, heading and separators included.

    Without this the first section — the handover, which nothing can reconstruct
    later — fills the cap on its own and the day lines it exists to sit beside
    never arrive. Measured on 2026-10-27: a 2,300-character handover rendered a
    1,484-character block with no today and no yesterday in it.
    """
    return sum(
        _room_for_first_line(section) + len(_SECTION_SEPARATOR) for section in sections
    )


def _fit_sections(sections: list[str]) -> str:
    """Wrap the sections that fit the cap, cutting one short so the rest still show.

    A section over its room is cut, and the sections after it are still rendered in
    what the cut left. The lines beyond a cut are not lost: they are in the day file,
    and the day lines a cut drops are one `SearchJournal` away, while the handover is
    the one part no later reader can reconstruct.
    """
    kept: list[str] = []
    for index, section in enumerate(sections):
        available = _room_for_next(kept)
        room = available - _reserve_for_later(sections[index + 1 :])
        if room < _room_for_first_line(section):
            # The reserves are unaffordable, so this section takes its whole turn
            # rather than being cut to less than a line.
            room = available
        if len(section) <= room:
            kept.append(section)
            continue
        if room > 0:
            kept.append(_cut_section(section, room))
    return _wrap_sections(kept)


def render_day_block(today: date | None = None) -> str | None:
    """The seam block: the newest handover, today's most important lines, and
    yesterday's two.

    The handover goes first because no later reader can reconstruct it. ``None``
    when there is no day file to read, or when journaling is off.
    """
    if not CFG.LLM_JOURNAL_ENABLED or not CFG.LLM_JOURNAL_DIR:
        return None
    current = today or datetime.now().date()
    yesterday = current - timedelta(days=1)
    today_text = _read_day(_day_file(current))
    yesterday_text = _read_day(_day_file(yesterday))
    if not today_text and not yesterday_text:
        return None
    sections: list[str] = []
    handover = _handover(today_text) or _handover(yesterday_text)
    if handover:
        sections.append("## From the last me, to the next me\n\n" + handover)
    today_entries = _top_entries(_day_entries(today_text), DAY_LINE_COUNT)
    if today_entries:
        sections.append(
            f"## Today ({current.isoformat()})\n\n"
            + "\n".join(f"- {_without_importance(entry)}" for entry in today_entries)
        )
    yesterday_entries = _top_entries(_day_entries(yesterday_text), YESTERDAY_LINE_COUNT)
    if yesterday_entries:
        sections.append(
            f"## Yesterday ({yesterday.isoformat()})\n\n"
            + "\n".join(
                f"- {_without_importance(entry)}" for entry in yesterday_entries
            )
        )
    if not sections:
        return None
    return _fit_sections(sections)


def render_live_context(
    ctx: AnyContext,
    model: "Any" = None,
    inject_journal_index: bool = False,
    first_message: str | None = None,
    previous_live_context: str | None = None,
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
        previous_live_context,
    )


async def render_live_context_async(
    ctx: AnyContext,
    model: "Any" = None,
    inject_journal_index: bool = False,
    first_message: str | None = None,
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
        inject_journal_index,
        model,
        first_message,
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
    inject_journal_index: bool,
    model: "Any" = None,
    first_message: str | None = None,
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

    if inject_journal_index:
        journal_block = render_journal_index(first_message)
        if journal_block:
            parts.append(journal_block)
        day_block = render_day_block()
        if day_block:
            parts.append(day_block)

    return "\n".join(parts)
