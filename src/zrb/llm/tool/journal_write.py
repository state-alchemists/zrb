"""Journal writers that own the on-disk format.

The model supplies *content*; this module derives paths, timestamps, index
entries and backlinks, which upholds these invariants by construction:

- **broken-link** — a link is only written after its target is confirmed on disk.
- **missing-backlink** — the reciprocal entry is inserted in the same call.
- **orphan** — every note is registered in its directory index, and every
  directory index is linked from the root index.
- **missing-index** — indexes are created on the way down to the leaf.
- **no lost update** — a coarse-grained lock on the root's `.lock` makes each
  writer's multi-file graph update atomic against a concurrent writer.
"""

import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.util.file_lock import hold_file_lock
from zrb.util.markdown import get_first_heading

NOTE_CATEGORIES = ("user", "preferences", "projects", "technical")
ACTIVITY_DIR = "activity-log"
_HISTORY_HEADING = "## History"
_HISTORY_MAX_ENTRIES = 3

# Which HUD section a note's one-line summary lands in.
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

    Call this BEFORE your reply on a turn that changed files or established a
    root cause, decision, or API quirk a later session would otherwise
    rediscover; then deliver the complete answer — never end the turn on the
    "Logged to ..." result. Skip greetings, clarifying questions, refusals,
    single lookups, and anything already recorded.

    Verify before recording: a wrong entry misleads every future session, and a
    number or an absence needs its source (`wc -l: 832`, `rg: 0 hits`) or stays
    out. Unless the user asked for the write, do not announce it. Use
    WriteJournalNote when the finding must be findable by topic.
    """
    with _open_journal() as root:
        now = datetime.now()
        day_file = _ensure_activity_path(root, now)
        file_note = ", ".join(files) if files else "—"
        entry = f"- {now.strftime('%H:%M')} — {summary.strip()}. Files: {file_note}."
        _insert_before_backlinks(day_file, entry)
        _git_commit(root, f"activity: {now:%Y-%m-%d %H:%M}")
        return f"Logged to {_posix_relpath(day_file, root)}"


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
                "certain it is free or that you mean to revise it, and wait "
                "for its result before this call — don't batch the two."
            )
        ),
    ],
    title: Annotated[
        str,
        Field(
            description=(
                "Short heading for the note; also the link label used by "
                "indexes and backlinks. Retitling an existing slug relabels "
                "its index entries."
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
                "about the user themselves or how they want to be worked with. "
                "Revising the note replaces the earlier line that ends in its "
                "`([note](…))` link."
            )
        ),
    ] = None,
) -> str:
    """Records a durable finding as a topic note, findable by search later.

    Call this BEFORE your reply, then deliver the complete answer — the write
    is recordkeeping, never the result. Write every field to stand alone: a
    future session finds the note by topic, with no memory of this
    conversation.

    Prefer it to LogActivity when a later session will need the finding by
    topic: who the user is or a preference they stated (highest value, usually
    said once — record it that turn), a root cause, a decision, or an API quirk.

    Record only what this session verified: an unchecked diagnosis, or a
    comparison with something you never saw, is a guess, and a wrong entry
    misleads every session that finds it. Skip anything already recorded —
    search first when unsure.

    This tool maintains the indexes, backlinks, and git history, so never edit
    journal files directly, even to tidy up after a write: revise here or
    remove with DeleteJournalNote. Unless the user asked for the write, do not
    announce it.
    """
    with _open_journal() as root:
        _check_category(category)
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
            _upsert_hud_line(
                root,
                _HUD_SECTION[category],
                hud_line.strip(),
                _posix_relpath(note_path, root),
            )
        _git_commit(root, f"write: {category}/{slug}")
        return f"Wrote {_posix_relpath(note_path, root)}"


write_journal_note.__name__ = "WriteJournalNote"


def delete_journal_note(
    category: Annotated[
        str, Field(description="One of: user, preferences, projects, technical.")
    ],
    slug: Annotated[
        str, Field(description="The note's existing filename, without `.md`.")
    ],
) -> str:
    """Deletes a note and every link to it: its category-index and Recent
    Insights entries, its pinned HUD line, and any Related/Backlinks line in
    other notes.

    There is no History fallback and you cannot undo it. Confirm the target
    first (Read it, or SearchJournal for it) rather than deleting a remembered
    or assumed slug, and wait for that result — don't batch the two. A human
    can recover the file from the journal's git history; you cannot. Unless
    the user asked for the deletion, do not announce it.
    """
    with _open_journal() as root:
        _check_category(category)
        note_path = os.path.join(root, category, f"{slug}.md")
        if not os.path.isfile(note_path):
            raise ValueError(
                f"[SYSTEM SUGGESTION]: no note at {category}/{slug}.md. "
                "SearchJournal for the correct slug, or omit the delete."
            )
        _scrub_links_to(root, note_path)
        os.remove(note_path)
        _git_commit(root, f"delete: {category}/{slug}")
        return f"Deleted {_posix_relpath(note_path, root)}"


delete_journal_note.__name__ = "DeleteJournalNote"


def _scrub_links_to(root: str, target_path: str) -> None:
    """Drop every `- [title](path)` or HUD `([note](path))` line elsewhere in
    *root* that resolves to *target_path*.

    ponytail: the label is matched greedily since a title may contain `]`;
    the end-anchored target always finds the last link on the line.

    ponytail: a full-tree scan per delete; add an index if the journal grows large.
    """
    link_re = re.compile(r"^- (?:\[.*\]\(([^)]+)\)|.*\(\[note\]\(([^)]+)\)\))\s*$")
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
                        os.path.join(
                            os.path.dirname(file_path),
                            match.group(1) or match.group(2),
                        )
                    )
                    if resolved == target_abs:
                        changed = True
                        continue
                kept.append(line)
            if changed:
                _write_text(file_path, "\n".join(kept).rstrip() + "\n")


@contextmanager
def _open_journal() -> Iterator[str]:
    """Yield the journal root with its tree in place, the lock held, and git
    initialized when `LLM_JOURNAL_GIT_ENABLED`."""
    root = ensure_journal_tree()
    # One root lock makes the multi-file update atomic against concurrent writers.
    with hold_file_lock(os.path.join(root, ".lock")):
        if CFG.LLM_JOURNAL_GIT_ENABLED:
            _ensure_journal_git(root)
        yield root


def _check_category(category: str) -> None:
    if category not in NOTE_CATEGORIES:
        raise ValueError(
            f"[SYSTEM SUGGESTION]: unknown category {category!r}. "
            f"Use one of: {', '.join(NOTE_CATEGORIES)}."
        )


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
    return root


def _ensure_journal_git(root: str) -> None:
    """Best-effort `git init` of the journal root. Never raises.

    Callers must hold the journal lock, or two first-time writers race."""
    if os.path.isdir(os.path.join(root, ".git")):
        return
    try:
        subprocess.run(
            ["git", "init", "--quiet", root],
            capture_output=True,
            check=False,
            timeout=CFG.LLM_GIT_CMD_TIMEOUT / 1000,
        )
    except (OSError, subprocess.SubprocessError):
        return
    _write_if_absent(os.path.join(root, ".gitignore"), ".lock\n")
    _git_commit(root, "init: journal tree")


def _git_commit(root: str, message: str) -> None:
    """Best-effort `git add -A && git commit` in *root*; silent on any failure.

    Inline `-c user.*` so no global git identity is needed."""
    if not os.path.isdir(os.path.join(root, ".git")):
        return
    git_identity = ["-c", "user.name=zrb-journal", "-c", "user.email=journal@zrb.local"]
    timeout = CFG.LLM_GIT_CMD_TIMEOUT / 1000
    try:
        subprocess.run(
            ["git", "-C", root, *git_identity, "add", "-A"],
            capture_output=True,
            check=False,
            timeout=timeout,
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
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        # Includes TimeoutExpired (GPG-sign prompt, stale index.lock).
        return


def _root_index_skeleton() -> str:
    directories = " · ".join(
        f"[{name}]({name}/index.md)" for name in (*NOTE_CATEGORIES, ACTIVITY_DIR)
    )
    # Order is load-bearing: the injected snapshot is capped and overflows from
    # the end, so the unbounded section goes last and evicts only itself.
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
    """Write the note, merging (never dropping) the existing ``## Backlinks``
    and ``## Related`` links, and appending the superseded Context/Finding to
    ``## History`` (capped at ``_HISTORY_MAX_ENTRIES``).
    """
    history = _merge_entries(
        _entries_under(note_path, _HISTORY_HEADING), _prior_revision_entry(note_path)
    )
    if len(history) > _HISTORY_MAX_ENTRIES:
        history = history[-_HISTORY_MAX_ENTRIES:]
    related = _merge_entries(
        _entries_under(note_path, "## Related"),
        [
            f"- [{_title_of(target)}]({_posix_relpath(target, os.path.dirname(note_path))})"
            for target in targets
        ],
    )
    # The directory index is always the first backlink.
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
    """The `- ` lines under *heading* in *path*, or `[]`."""
    lines = _read_text(path).splitlines()
    if heading not in lines:
        return []
    start, end = _section_bounds(lines, heading)
    return [line for line in lines[start:end] if line.startswith("- ")]


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


def _posix_relpath(path: str, start: str) -> str:
    """`os.path.relpath` with `/` separators, for portable markdown links."""
    return os.path.relpath(path, start).replace(os.sep, "/")


def _add_backlink(target: str, source_path: str, source_title: str) -> None:
    rel = _posix_relpath(source_path, os.path.dirname(target))
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
    rel = _posix_relpath(note_path, os.path.dirname(index_path))
    _register_link(index_path, rel, title, heading=heading)


def _register_link(
    index_path: str, rel_target: str, label: str, heading: str | None = None
) -> None:
    """Append `- [label](rel_target)` to an index, under *heading* if given.

    An existing entry for the target is relabelled in place; duplicates are dropped.
    """
    entry = f"- [{label}]({rel_target})"
    text = _read_text(index_path)
    same_target = re.compile(rf"- \[.*\]\({re.escape(rel_target)}\)")
    kept: list[str] = []
    found = False
    for line in text.splitlines():
        if same_target.fullmatch(line):
            if not found:
                kept.append(entry)
                found = True
            continue
        kept.append(line)
    if found:
        updated = "\n".join(kept) + "\n"
        if updated != text:
            _write_text(index_path, updated)
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
    start, end = _section_bounds(lines, heading)
    body = [line for line in lines[start:end] if line.strip()]
    body.append(entry)
    return "\n".join([*lines[:start], "", *body, "", *lines[end:]]).rstrip() + "\n"


def _section_bounds(lines: list[str], heading: str) -> tuple[int, int]:
    """`[start, end)` of the body under *heading*, up to the next `## `."""
    start = lines.index(heading) + 1
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return start, end


def _upsert_hud_line(root: str, section: str, line: str, note_rel: str) -> None:
    """Pin *line* under *section*, replacing any earlier line from the same note.

    Lines are keyed by their trailing note link; an unlinked line is replaced
    only when identical to the new one.
    """
    own = f" ([note]({note_rel}))"
    base = f"- {line.removeprefix('- ')}"
    entry = f"{base}{own}"
    index_path = os.path.join(root, "index.md")
    text = _read_text(index_path)
    if entry in text:
        return
    heading = f"## {section}"
    lines = text.splitlines()
    if heading in lines:
        start, end = _section_bounds(lines, heading)
        kept = [ln for ln in lines[start:end] if not ln.endswith(own) and ln != base]
        text = "\n".join([*lines[:start], *kept, *lines[end:]]) + "\n"
    text = _append_under_heading(text, heading, entry)
    text = _cap_section_entries(
        text, heading, CFG.LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION
    )
    _write_text(index_path, text)


def _cap_section_entries(text: str, heading: str, max_entries: int) -> str:
    """Keep only the newest *max_entries* lines under *heading* (`<= 0` uncapped).

    For HUD sections only; catalogs like `Recent Insights` stay complete.
    """
    if max_entries <= 0:
        return text
    lines = text.splitlines()
    if heading not in lines:
        return text
    start, end = _section_bounds(lines, heading)
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
    """The current Context/Finding as a dated `## History` bullet, or `[]`."""
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
    return (
        get_first_heading(_read_text(path))
        or os.path.splitext(os.path.basename(path))[0]
    )


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
