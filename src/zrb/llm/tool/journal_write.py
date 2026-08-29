"""Journal writers that own the on-disk format.

The model supplies *content*; this module supplies *structure*. Paths,
timestamps, index registration, and reciprocal backlinks are derived here, which
is what makes these four invariants unviolatable rather than merely checkable:

- **broken-link** — a link is only written after its target is confirmed on disk.
- **missing-backlink** — the reciprocal entry is inserted in the same call.
- **orphan** — every note is registered in its directory index, and every
  directory index is linked from the root index.
- **missing-index** — indexes are created on the way down to the leaf.
"""

import os
import re
from datetime import datetime

from zrb.config.config import CFG

NOTE_CATEGORIES = ("user", "preferences", "projects", "technical")
ACTIVITY_DIR = "activity-log"

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


def log_activity(summary: str, files: list[str] | None = None) -> str:
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

    Writing is silent; do not announce it. The date, the time, and the file path
    are derived here, so pass only what happened. `files` are paths you touched.

    Use WriteJournalNote instead when the finding needs to be findable by topic.
    """
    root = ensure_journal_tree()
    now = datetime.now()
    day_file = _ensure_activity_path(root, now)
    file_note = ", ".join(files) if files else "—"
    entry = f"- {now.strftime('%H:%M')} — {summary.strip()}. Files: {file_note}."
    _insert_before_backlinks(day_file, entry)
    return f"Logged to {os.path.relpath(day_file, root)}"


log_activity.__name__ = "LogActivity"


def write_journal_note(
    category: str,
    slug: str,
    title: str,
    context: str,
    finding: str,
    source: str,
    links: list[str] | None = None,
    hud_line: str | None = None,
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

    `category` is one of: user, preferences, projects, technical.
    `slug` is kebab-case and becomes the filename.
    `context` says when the finding applies; `finding` is the durable fact;
    `source` is a file:line, commit, or URL backing it.
    `links` are journal-root-relative paths of related notes (e.g.
    `technical/retry-policy.md`); each gets a reciprocal backlink automatically.
    `hud_line` is a one-line compression pinned to the always-injected index, so
    the fact survives without a search — use it for anything about the user
    themselves or how they want to be worked with.

    Writing is silent; do not announce it.
    """
    root = ensure_journal_tree()
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
        os.path.join(root, "index.md"), note_path, title, heading="## Recent Insights"
    )
    if hud_line:
        _upsert_hud_line(root, _HUD_SECTION[category], hud_line.strip())
    return f"Wrote {os.path.relpath(note_path, root)}"


write_journal_note.__name__ = "WriteJournalNote"


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

    Merging is the conservative direction: a link is only ever added here, and
    ``_resolve_links`` has already confirmed each new target exists on disk.
    """
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
    lines = _read_text(path).splitlines()
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
    _write_text(index_path, _append_under_heading(text, f"## {section}", entry))


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
