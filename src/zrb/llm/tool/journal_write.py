"""Journal writers that own the on-disk format.

The model supplies *content*; this module supplies *structure*. Paths,
timestamps, index registration, and reciprocal backlinks are derived here, which
is what makes these five invariants unviolatable rather than merely checkable:

- **broken-link** — a link is only written after its target is confirmed on disk.
- **missing-backlink** — the reciprocal entry is inserted in the same call.
- **orphan** — every note is registered in its directory index, and every
  directory index is linked from the root index.
- **missing-index** — indexes are created on the way down to the leaf.
- **no lost update** — a coarse-grained lock (`_journal_lock`) makes each
  writer's multi-file graph update atomic against a concurrent writer.
"""

import os
import re
import subprocess
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated

from pydantic import Field

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None  # ponytail: POSIX-only lock; non-POSIX falls back to unlocked

from zrb.config.config import CFG

NOTE_CATEGORIES = ("user", "preferences", "projects", "technical")
ACTIVITY_DIR = "activity-log"
_HISTORY_HEADING = "## History"
_HISTORY_MAX_ENTRIES = 3

# Which HUD section a note's one-line summary lands in. `projects` and
# `technical` carry situational facts rather than identity or taste, so they
# share the constraints section.
_HUD_SECTION = {
    "user": "User",
    "preferences": "Preferences",
    "projects": "Active Constraints",
    "technical": "Active Constraints",
}
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BACKLINKS_HEADING = "## Backlinks"


def log_activity(
    summary: Annotated[
        str,
        Field(
            description=(
                "One line of what happened. The date, time, and file path are "
                "derived here — pass only the summary itself."
            )
        ),
    ],
    files: Annotated[
        list[str] | None,
        Field(description="Paths you touched this turn, if any."),
    ] = None,
) -> str:
    """Records one line of work in the journal's activity log.

    Call this BEFORE composing your reply on any turn that changed files, or
    that established a root cause, decision, or API quirk a later session would
    otherwise rediscover. The write is recordkeeping, never the user-facing
    result: after it, deliver the complete final answer — never end the turn
    with only the "Logged to ..." return value.

    Skip greetings, clarifying questions, refusals,
    single lookups, and anything already recorded. Verify before recording — a
    wrong entry misleads every future session, and a number or an absence needs
    its source (`wc -l: 832`, `rg: 0 hits`) or stays out.

    Writing is silent; do not announce it.

    Use WriteJournalNote instead when the finding needs to be findable by topic.
    """
    root = ensure_journal_tree()
    with _journal_lock(root):
        now = datetime.now()
        day_file = _ensure_activity_path(root, now)
        file_note = ", ".join(files) if files else "—"
        entry = f"- {now.strftime('%H:%M')} — {summary.strip()}. Files: {file_note}."
        _insert_before_backlinks(day_file, entry)
        _git_commit(root, f"activity: {now:%Y-%m-%d %H:%M}")
        return f"Logged to {os.path.relpath(day_file, root)}"


log_activity.__name__ = "LogActivity"


def write_journal_note(
    category: Annotated[
        str, Field(description="One of: user, preferences, projects, technical.")
    ],
    slug: Annotated[
        str,
        Field(
            description=(
                "Kebab-case; becomes the filename. Reusing an existing slug "
                "overwrites that note — the previous Context/Finding is kept "
                "as one bounded History entry, not preserved in full. Call "
                "SearchJournal for this slug or topic first if you are not "
                "certain it is free or that you mean to revise it."
            )
        ),
    ],
    title: Annotated[
        str,
        Field(
            description=(
                "Short heading for the note; also the link label used by "
                "indexes and backlinks."
            )
        ),
    ],
    context: Annotated[str, Field(description="When the finding applies.")],
    finding: Annotated[
        str,
        Field(
            description=(
                "The durable fact itself, stated so a future session with no "
                "memory of this conversation understands it standalone."
            )
        ),
    ],
    source: Annotated[
        str, Field(description="A file:line, commit hash, or URL backing the finding.")
    ],
    links: Annotated[
        list[str] | None,
        Field(
            description=(
                "Journal-root-relative paths of related notes (e.g. "
                "`technical/retry-policy.md`); each gets a reciprocal "
                "backlink automatically."
            )
        ),
    ] = None,
    hud_line: Annotated[
        str | None,
        Field(
            description=(
                "One-line compression pinned to the always-injected index, "
                "so the fact survives without a search — use it for anything "
                "about the user themselves or how they want to be worked with."
            )
        ),
    ] = None,
) -> str:
    """Records a durable finding as a topic note, findable by search later.

    Call this BEFORE composing your reply, then deliver the complete final
    answer — the write is recordkeeping, never the user-facing result. The note
    must stand alone: a future session finds it by topic, so every field reads
    as if the conversation is gone.

    Use this over LogActivity when a later session will need the finding by
    topic rather than by date: who the user is or a preference they stated
    (highest value, usually said exactly once — record it the turn it is said),
    a root cause, a decision, or an API quirk.

    Skip anything already recorded to your satisfaction — search first when
    unsure, rather than writing a speculative or duplicate note. Verify before
    recording: a wrong or spurious entry misleads every future session that
    finds it.

    Writing is silent; do not announce it.
    """
    root = ensure_journal_tree()
    with _journal_lock(root):
        if category not in NOTE_CATEGORIES:
            raise ValueError(
                f"[SYSTEM SUGGESTION]: unknown category {category!r}. "
                f"Use one of: {', '.join(NOTE_CATEGORIES)}."
            )
        if not _SLUG_RE.match(slug):
            raise ValueError(
                f"[SYSTEM SUGGESTION]: slug {slug!r} must be kebab-case "
                "(lowercase letters, digits, single hyphens)."
            )
        targets = _resolve_links(root, links or [])
        note_path = os.path.join(root, category, f"{slug}.md")
        _write_note_file(note_path, slug, title, context, finding, source, targets)
        for target in targets:
            _add_backlink(target, note_path, title)
        _register_in_index(os.path.join(root, category, "index.md"), note_path, title)
        _register_in_index(
            os.path.join(root, "index.md"),
            note_path,
            title,
            heading="## Recent Insights",
        )
        if hud_line:
            _upsert_hud_line(root, _HUD_SECTION[category], hud_line.strip())
        _git_commit(root, f"write: {category}/{slug}")
        return f"Wrote {os.path.relpath(note_path, root)}"


write_journal_note.__name__ = "WriteJournalNote"


def delete_journal_note(
    category: Annotated[
        str, Field(description="One of: user, preferences, projects, technical.")
    ],
    slug: Annotated[
        str, Field(description="The note's existing filename, without `.md`.")
    ],
) -> str:
    """Deletes a note and scrubs every reference to it across the journal.

    Removes the note file, then walks every other file in the journal and
    drops any markdown link line resolving to it — its entry in the category
    index, in the root index's Recent Insights, and any `## Related`/
    `## Backlinks` line another note held pointing here. A textual scrub
    rather than precise Related/Backlinks bookkeeping: every link in this
    journal is a deterministic `- [title](relative/path.md)` line, so
    removing any line whose link resolves to this file is as precise as
    tracking the graph structurally.

    Unlike WriteJournalNote, there is no History fallback here, and this tool
    cannot undo the removal itself — confirm the target's actual content
    first (Read it, or SearchJournal for it) rather than deleting on a
    remembered or assumed slug. If the journal is git-backed, a human may
    still recover the file from its git history outside this tool, but that
    is not something you can do yourself. Silent otherwise: do not announce
    the deletion in your reply.
    """
    root = ensure_journal_tree()
    with _journal_lock(root):
        if category not in NOTE_CATEGORIES:
            raise ValueError(
                f"[SYSTEM SUGGESTION]: unknown category {category!r}. "
                f"Use one of: {', '.join(NOTE_CATEGORIES)}."
            )
        note_path = os.path.join(root, category, f"{slug}.md")
        if not os.path.isfile(note_path):
            raise ValueError(
                f"[SYSTEM SUGGESTION]: no note at {category}/{slug}.md. "
                "SearchJournal for the correct slug, or omit the delete."
            )
        _scrub_links_to(root, note_path)
        os.remove(note_path)
        _git_commit(root, f"delete: {category}/{slug}")
        return f"Deleted {os.path.relpath(note_path, root)}"


delete_journal_note.__name__ = "DeleteJournalNote"


def _scrub_links_to(root: str, target_path: str) -> None:
    """Drop every markdown link line elsewhere in *root* resolving to
    *target_path*, rewriting each changed file once.

    ponytail: a full-tree scan per delete — the journal is personal notes,
    not a corpus, so O(files) here is cheap; upgrade to an index if this
    journal ever grows past a size where that stops being true.
    """
    link_re = re.compile(r"^- \[[^\]]*\]\(([^)]+)\)\s*$")
    target_abs = os.path.abspath(target_path)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            file_path = os.path.join(dirpath, filename)
            if os.path.abspath(file_path) == target_abs:
                continue
            text = _read_text(file_path)
            if not text:
                continue
            changed = False
            kept: list[str] = []
            for line in text.splitlines():
                match = link_re.match(line)
                if match:
                    resolved = os.path.abspath(
                        os.path.join(os.path.dirname(file_path), match.group(1))
                    )
                    if resolved == target_abs:
                        changed = True
                        continue
                kept.append(line)
            if changed:
                _write_text(file_path, "\n".join(kept).rstrip() + "\n")


@contextmanager
def _journal_lock(root: str):
    """Coarse-grained advisory lock over the whole journal root, held for the
    duration of one write call. Makes the multi-file graph update (note +
    backlinks + two indexes) atomic as a unit, not just each file write in
    isolation — closes the lost-update race between concurrent writers (a
    sub-agent and the main session, or the compliance-judge hook racing the
    turn it followed). POSIX-only; falls back to a no-op where `fcntl` is
    unavailable, matching the previous unlocked behavior there.
    """
    if fcntl is None:
        yield
        return
    lock_path = os.path.join(root, ".lock")
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def ensure_journal_tree() -> str:
    """Create the journal root, its five directories, and their indexes."""
    journal_dir = CFG.LLM_JOURNAL_DIR
    if not journal_dir:
        raise ValueError(
            "[SYSTEM SUGGESTION]: journal directory is not configured "
            "(LLM_JOURNAL_DIR is unset). Report this rather than retrying."
        )
    root = os.path.abspath(os.path.expanduser(journal_dir))
    os.makedirs(root, exist_ok=True)
    for name in (*NOTE_CATEGORIES, ACTIVITY_DIR):
        os.makedirs(os.path.join(root, name), exist_ok=True)
        _write_if_absent(
            os.path.join(root, name, "index.md"),
            f"# {name.replace('-', ' ').title()}\n",
        )
    _write_if_absent(os.path.join(root, "index.md"), _root_index_skeleton())
    if CFG.LLM_JOURNAL_GIT_ENABLED:
        _ensure_journal_git(root)
    return root


def _ensure_journal_git(root: str) -> None:
    """Best-effort `git init` for the journal root, so writes/deletes become
    real, unbounded commits instead of relying only on the in-file History
    block (capped at `_HISTORY_MAX_ENTRIES`). Never raises: a missing `git`
    binary or a failed init leaves journaling exactly as it was before this
    existed — same fallback spirit as the `fcntl`-unavailable branch above."""
    if os.path.isdir(os.path.join(root, ".git")):
        return
    try:
        subprocess.run(
            ["git", "init", "--quiet", root], capture_output=True, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return
    _write_if_absent(os.path.join(root, ".gitignore"), ".lock\n")
    _git_commit(root, "init: journal tree")


def _git_commit(root: str, message: str) -> None:
    """Best-effort `git add -A && git commit`, scoped to *root*. Silent on any
    failure (no git binary, nothing to commit, git not initialized here) —
    this is a durability backstop, never a new way for a journal call to
    fail. Inline `-c user.*` flags so it never depends on the environment's
    global git identity being configured."""
    if not os.path.isdir(os.path.join(root, ".git")):
        return
    git_identity = ["-c", "user.name=zrb-journal", "-c", "user.email=journal@zrb.local"]
    try:
        subprocess.run(
            ["git", "-C", root, *git_identity, "add", "-A"],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            [
                "git",
                "-C",
                root,
                *git_identity,
                "commit",
                "-m",
                message,
                "--allow-empty-message",
                "--quiet",
            ],
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return


def _root_index_skeleton() -> str:
    directories = " · ".join(
        f"[{name}]({name}/index.md)" for name in (*NOTE_CATEGORIES, ACTIVITY_DIR)
    )
    # Order is load-bearing: the injected snapshot is capped and overflows from
    # the end, so the unbounded section goes last and only ever evicts itself.
    return (
        "# Journal\n\n"
        "## User\n\n"
        "## Preferences\n\n"
        "## Active Constraints\n\n"
        f"## Directories\n\n- {directories}\n\n"
        "## Recent Insights\n"
    )


def _ensure_activity_path(root: str, now: datetime) -> str:
    """Create year/month/day indexes down to the day file, linking each level."""
    year, month, day = (
        now.strftime("%Y"),
        now.strftime("%Y-%m"),
        now.strftime("%Y-%m-%d"),
    )
    activity = os.path.join(root, ACTIVITY_DIR)
    year_dir = os.path.join(activity, year)
    month_dir = os.path.join(year_dir, month)
    os.makedirs(month_dir, exist_ok=True)
    _write_if_absent(os.path.join(year_dir, "index.md"), f"# {year}\n")
    _write_if_absent(os.path.join(month_dir, "index.md"), f"# {month}\n")
    _register_link(os.path.join(activity, "index.md"), f"{year}/index.md", year)
    _register_link(os.path.join(year_dir, "index.md"), f"{month}/index.md", month)
    _register_link(os.path.join(month_dir, "index.md"), f"{day}.md", day)
    day_file = os.path.join(month_dir, f"{day}.md")
    _write_if_absent(
        day_file, f"# {day}\n\n{_BACKLINKS_HEADING}\n\n- [month index](index.md)\n"
    )
    return day_file


def _write_note_file(
    note_path: str,
    slug: str,
    title: str,
    context: str,
    finding: str,
    source: str,
    targets: list[str],
) -> None:
    """Write the note, preserving the link graph an earlier revision accumulated.

    A note gets re-written whenever its finding is refined, and the *whole* file
    is composed from the arguments — which is why the two link blocks have to be
    merged rather than rebuilt. Neither is the caller's to supply on an update:

    * ``## Backlinks`` is written by *other* notes, via ``_add_backlink``. A
      plain truncate dropped every one of them, so linking A→B and then updating
      B left B with no way back to A. That is the ``missing-backlink`` invariant
      this module claims to make unviolatable, violated by its own writer.
    * ``## Related`` holds the forward links. Dropping those while the targets
      keep their backlinks is the same break seen from the other end — a
      backlink pointing at a note that no longer claims the relationship.
    * ``## History`` holds prior Context/Finding pairs, capped at
      ``_HISTORY_MAX_ENTRIES``. Populated from ``_prior_revision_entry``, read
      before this function overwrites the file — otherwise a belief change
      (a decision reversed, a root cause corrected) leaves no trace of what
      was believed before, or when it changed.

    Merging is the conservative direction: a link is only ever added here, and
    ``_resolve_links`` has already confirmed each new target exists on disk.
    """
    # Read before the rewrite below discards it: the note's prior revision,
    # if any, becomes one bounded History entry (belief changes are traceable
    # instead of silently overwritten — see `_prior_revision_entry`).
    history = _merge_entries(
        _entries_under(note_path, _HISTORY_HEADING), _prior_revision_entry(note_path)
    )
    if len(history) > _HISTORY_MAX_ENTRIES:
        history = history[-_HISTORY_MAX_ENTRIES:]
    related = _merge_entries(
        _entries_under(note_path, "## Related"),
        [
            f"- [{_title_of(target)}]({os.path.relpath(target, os.path.dirname(note_path))})"
            for target in targets
        ],
    )
    # The directory index is what makes this note reachable from the root, so it
    # is the note's first backlink by construction.
    backlinks = _merge_entries(
        _entries_under(note_path, _BACKLINKS_HEADING), ["- [index](index.md)"]
    )
    lines = [
        "---",
        f"slug: {slug}",
        "---",
        f"# {title}",
        "",
        f"**Context:** {context}",
        f"**Finding:** {finding}",
        f"**Source:** {source}",
        "",
    ]
    if history:
        lines.append(_HISTORY_HEADING)
        lines.append("")
        lines.extend(history)
        lines.append("")
    if related:
        lines.append("## Related")
        lines.append("")
        lines.extend(related)
        lines.append("")
    lines.append(_BACKLINKS_HEADING)
    lines.append("")
    lines.extend(backlinks)
    lines.append("")
    _write_text(note_path, "\n".join(lines))


def _entries_under(path: str, heading: str) -> list[str]:
    """The `- […](…)` lines already listed under *heading* in an existing file.

    Empty for a file that does not exist yet, or that has no such heading.
    """
    return _entries_under_text(_read_text(path), heading)


def _entries_under_text(text: str, heading: str) -> list[str]:
    """`_entries_under`, given the file's content directly (no re-read)."""
    lines = text.splitlines()
    if heading not in lines:
        return []
    start = lines.index(heading) + 1
    entries: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.startswith("- "):
            entries.append(line)
    return entries


def _merge_entries(existing: list[str], new: list[str]) -> list[str]:
    """Existing entries in their original order, then any genuinely new ones."""
    merged = list(existing)
    for entry in new:
        if entry not in merged:
            merged.append(entry)
    return merged


def _resolve_links(root: str, links: list[str]) -> list[str]:
    """Turn journal-relative link paths into absolute ones, rejecting misses."""
    resolved: list[str] = []
    for link in links:
        candidate = os.path.abspath(os.path.join(root, link))
        if not _is_inside(candidate, root):
            raise ValueError(
                f"[SYSTEM SUGGESTION]: link {link!r} points outside the journal. "
                "Use a path relative to the journal root."
            )
        if not os.path.isfile(candidate):
            raise ValueError(
                f"[SYSTEM SUGGESTION]: link target {link!r} does not exist. "
                "SearchJournal for the correct path, or omit the link."
            )
        resolved.append(candidate)
    return resolved


def _is_inside(path: str, parent: str) -> bool:
    return path == parent or path.startswith(f"{parent}{os.sep}")


def _add_backlink(target: str, source_path: str, source_title: str) -> None:
    rel = os.path.relpath(source_path, os.path.dirname(target))
    entry = f"- [{source_title}]({rel})"
    text = _read_text(target)
    if entry in text:
        return
    if _BACKLINKS_HEADING not in text:
        text = f"{text.rstrip()}\n\n{_BACKLINKS_HEADING}\n"
    _write_text(target, f"{text.rstrip()}\n{entry}\n")


def _register_in_index(
    index_path: str, note_path: str, title: str, heading: str | None = None
) -> None:
    rel = os.path.relpath(note_path, os.path.dirname(index_path))
    _register_link(index_path, rel, title, heading=heading)


def _register_link(
    index_path: str, rel_target: str, label: str, heading: str | None = None
) -> None:
    """Append `- [label](rel_target)` to an index, under *heading* if given."""
    entry = f"- [{label}]({rel_target})"
    text = _read_text(index_path)
    if entry in text:
        return
    if heading is None:
        body = text.rstrip()
        gap = "\n" if body.rsplit("\n", 1)[-1].startswith("- ") else "\n\n"
        _write_text(index_path, f"{body}{gap}{entry}\n")
        return
    _write_text(index_path, _append_under_heading(text, heading, entry))


def _append_under_heading(text: str, heading: str, entry: str) -> str:
    lines = text.splitlines()
    if heading not in lines:
        return f"{text.rstrip()}\n\n{heading}\n\n{entry}\n"
    start = lines.index(heading) + 1
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    body = [line for line in lines[start:end] if line.strip()]
    body.append(entry)
    return "\n".join([*lines[:start], "", *body, "", *lines[end:]]).rstrip() + "\n"


def _upsert_hud_line(root: str, section: str, line: str) -> None:
    entry = line if line.startswith("- ") else f"- {line}"
    index_path = os.path.join(root, "index.md")
    text = _read_text(index_path)
    if entry in text:
        return
    text = _append_under_heading(text, f"## {section}", entry)
    text = _cap_section_entries(
        text, f"## {section}", CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION
    )
    _write_text(index_path, text)


def _cap_section_entries(text: str, heading: str, max_entries: int) -> str:
    """Keep only the newest *max_entries* bullet lines under *heading*,
    dropping the oldest first (entries are always appended at the end).
    `<= 0` means uncapped.

    Scoped to HUD sections only (User/Preferences/Active Constraints) by
    every caller — `Recent Insights` and category indexes must stay uncapped,
    since their completeness is what makes them a trustworthy full catalog
    for direct Read (ADR-0055).
    """
    if max_entries <= 0:
        return text
    lines = text.splitlines()
    if heading not in lines:
        return text
    start = lines.index(heading) + 1
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    body = [line for line in lines[start:end] if line.strip()]
    if len(body) <= max_entries:
        return text
    body = body[-max_entries:]
    return "\n".join([*lines[:start], "", *body, "", *lines[end:]]).rstrip() + "\n"


def _insert_before_backlinks(path: str, entry: str) -> None:
    """Append an entry above the trailing Backlinks block, which stays last."""
    text = _read_text(path)
    if entry in text:
        return
    if _BACKLINKS_HEADING not in text:
        _write_text(path, f"{text.rstrip()}\n{entry}\n")
        return
    head, _, tail = text.partition(_BACKLINKS_HEADING)
    _write_text(path, f"{head.rstrip()}\n{entry}\n\n{_BACKLINKS_HEADING}{tail}")


def _prior_revision_entry(note_path: str) -> list[str]:
    """The just-superseded Context/Finding as one dated `## History` bullet,
    or `[]` for a brand-new note. Must be read before `_write_note_file`
    overwrites *note_path* — this function only reads."""
    text = _read_text(note_path)
    if not text:
        return []
    old_context = _field(text, "**Context:**")
    old_finding = _field(text, "**Finding:**")
    if old_context is None and old_finding is None:
        return []
    date = datetime.now().strftime("%Y-%m-%d")
    return [f"- {date}: {old_context or '—'} — {old_finding or '—'}"]


def _field(text: str, prefix: str) -> str | None:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _title_of(path: str) -> str:
    for line in _read_text(path).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return os.path.splitext(os.path.basename(path))[0]


def _write_if_absent(path: str, content: str) -> None:
    if not os.path.exists(path):
        _write_text(path, content)


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
