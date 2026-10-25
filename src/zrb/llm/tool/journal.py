import json
import os
import re
import shutil
import subprocess
from typing import Annotated, Any

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.journal_index_name import resolve_journal_index_name
from zrb.llm.tool.journal_write import NOTE_CATEGORIES
from zrb.util.markdown import get_first_heading
from zrb.util.truncate import truncate_text

# Characters that make a query a regex instead of plain words.
_REGEX_META = frozenset("\\^$.*+?()[]{}|")

# Words too common to say what a query is about, dropped before matching titles.
_STOP_WORDS = frozenset("""
    a an and are as at be been but by can did do does for from had has have how
    i if in into is it its just me my not of on or our so than that the their
    them then there these they this to too was we were what when where which
    who why will with would you your
    """.split())

# One file is shown at most this many times: a note that says "compaction" on
# twelve lines would otherwise be the whole result, and the note that is *about*
# compaction would never be seen.
_ROWS_PER_FILE = 3

# How many files a result names. A word that appears in every note would
# otherwise put every note in the answer.
MAX_FILES = 5

# The whole result, so a broad query stays readable.
_MAX_ROWS = 60

# Where a file sits in the ranking. A title match is a note *about* the query; a
# note that merely mentions it still beats the indexes and the activity log,
# which mention everything.
_TITLE_MATCH = 0
_NOTE = 1
_INDEX = 2
_ACTIVITY = 3


def search_journal(
    query: Annotated[
        str,
        Field(
            description=(
                "What to look for. Plain words are read as any-of (filler "
                "words dropped; a file holding more of them ranks first). "
                "Anything containing regex metacharacters is a regex."
            )
        ),
    ],
    case_sensitive: Annotated[
        bool, Field(description="False (default): case-insensitive search.")
    ] = False,
) -> dict[str, Any]:
    """
    Searches the journal for a regex pattern or for a set of words.

    Returns matching lines with file names and line numbers, notes whose title
    matches first, then other notes, then the indexes and the activity log. A
    zero-hit search suggests titles under `did_you_mean` and is not proof the
    topic was never recorded: try those or a synonym before concluding.

    Call this before WriteJournalNote or DeleteJournalNote whenever you are
    not certain a slug is free, or that it names the note you intend to touch.
    Wait for this result before issuing that write or delete — don't batch
    the two calls. Search before SupersedeJournalNote too: its reason should
    name the note that replaced this one.
    """
    journal_dir = CFG.LLM_JOURNAL_DIR
    if not journal_dir:
        return {
            "error": (
                "Journal directory is not configured (LLM_JOURNAL_DIR is "
                "unset). [SYSTEM SUGGESTION]: Report this rather than "
                "retrying."
            )
        }

    abs_dir = os.path.abspath(os.path.expanduser(journal_dir))
    if not os.path.isdir(abs_dir):
        # A never-written journal is empty, not broken: create it and report
        # an empty search.
        try:
            os.makedirs(abs_dir, exist_ok=True)
        except OSError as e:
            return {"error": f"Cannot create journal directory {journal_dir}: {e}"}
        return {"summary": "No matches found.", "results": []}

    words = _query_words(query)
    if words:
        found = _matches_any_word(words, abs_dir, case_sensitive)
    else:
        found = _all_matches(query, abs_dir, case_sensitive)
    if isinstance(found, dict):
        return found
    if not found:
        return _no_matches(query, abs_dir)
    return _format_results(found, abs_dir, words or [query], case_sensitive)


search_journal.__name__ = "SearchJournal"


def _query_words(query: str) -> list[str]:
    """The words of a plain multi-word *query*, or `[]` when it is a regex.

    A question is longer than any title and carries no regex syntax, so reading
    it as one literal string matched nothing at all. Several plain words now
    mean "any of these words", and the words that say nothing about the subject
    — `the`, `of`, `how` — are dropped first. Any-of rather than all-of is a
    measurement, not a preference: requiring every word found 2 of 8
    question-style queries against 8 of 8, because a question is prose and no
    note repeats its words verbatim. Precision comes from the ranking instead —
    a file holding more of the words sorts first. A single word, or anything
    with a metacharacter in it, stays a regex."""
    if any(character in _REGEX_META for character in query):
        return []
    words = [word for word in re.split(r"\s+", query.strip()) if word]
    if len(words) < 2:
        return []
    significant = [word for word in words if word.lower() not in _STOP_WORDS]
    return significant if len(significant) > 1 else words


def _matches_any_word(
    words: list[str], abs_dir: str, case_sensitive: bool
) -> "list[tuple[str, int, str]] | dict[str, Any]":
    """The matching lines of every file holding any of *words*, or a failure."""
    found: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int]] = set()
    for word in words:
        matches = _all_matches(word, abs_dir, case_sensitive)
        if isinstance(matches, dict):
            return matches
        for match in matches:
            key = (match[0], match[1])
            if key in seen:
                continue
            seen.add(key)
            found.append(match)
    return found


def _matches_every_word(
    words: list[str], abs_dir: str, case_sensitive: bool
) -> "list[tuple[str, int, str]] | dict[str, Any]":
    """The matching lines of every file that holds every one of *words*.

    Kept because it is the alternative `_matches_any_word` was chosen over, and
    the choice was measured rather than argued: requiring every word found 2 of
    8 question-style queries against 8 of 8 for any-of, since a question is
    prose and no note repeats it verbatim. Not on the search path — the test
    `test_requiring_every_word_would_miss_the_note_a_question_asks_for` pins
    the difference, so a later reader does not have to take this on faith.

    One pass per word, intersected by file, because the regex engine here has
    no look-around to ask for all of them at once."""
    per_word: "list[dict[str, list[tuple[str, int, str]]]]" = []
    for word in words:
        found = _all_matches(word, abs_dir, case_sensitive)
        if isinstance(found, dict):
            return found
        grouped: dict[str, list[tuple[str, int, str]]] = {}
        for match in found:
            grouped.setdefault(match[0], []).append(match)
        per_word.append(grouped)
    keep = set(per_word[0])
    for grouped in per_word[1:]:
        keep &= set(grouped)
    if not keep:
        return []
    return [
        match
        for grouped in per_word
        for path, rows in grouped.items()
        if path in keep
        for match in rows
    ]


def _all_matches(
    query: str, abs_dir: str, case_sensitive: bool
) -> "list[tuple[str, int, str]] | dict[str, Any]":
    """Every line of the journal matching *query*, or a failure to report."""
    if shutil.which("rg"):
        # ripgrep validates its own dialect (`\p{L}` is valid there).
        return _rg_matches(query, abs_dir, case_sensitive)
    try:
        pattern = re.compile(query, 0 if case_sensitive else re.IGNORECASE)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {e}"}
    return _python_matches(pattern, abs_dir)


def _rg_matches(
    query: str, abs_dir: str, case_sensitive: bool
) -> "list[tuple[str, int, str]] | dict[str, Any]":
    cmd = ["rg", "--json", "--no-messages"]
    if not case_sensitive:
        cmd.append("--ignore-case")
    cmd.extend(["--", query, abs_dir])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"error": f"rg failed: {e}"}
    if proc.returncode == 2:
        # A regex that does not compile is the query's fault, not the journal's.
        return {"error": f"Invalid regex pattern: {proc.stderr.strip()}"}
    return _parse_rg_json(proc.stdout)


def _parse_rg_json(stdout: str) -> list[tuple[str, int, str]]:
    """`(path, line, content)` for each match event of `rg --json`.

    Structured output, because `path:line:content` is ambiguous: a path may
    hold `:` (a Windows drive, or a Unix `note:12:x.md`).
    """
    matches: list[tuple[str, int, str]] = []
    for raw in stdout.splitlines():
        try:
            event = json.loads(raw)
        except ValueError:
            continue
        if event.get("type") != "match":
            continue
        data = event["data"]
        path = data["path"].get("text")
        content = data["lines"].get("text")
        if path is None or content is None:  # non-UTF-8 bytes
            continue
        matches.append((path, data["line_number"], content.rstrip("\r\n")))
    return matches


def _python_matches(pattern: re.Pattern, abs_dir: str) -> list[tuple[str, int, str]]:
    raw_lines: list[tuple[str, int, str]] = []
    for root, dirs, files in os.walk(abs_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if filename.startswith("."):
                continue
            file_path = os.path.join(root, filename)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.search(line):
                            raw_lines.append((file_path, line_num, line.rstrip()))
            except OSError:
                pass
    return raw_lines


def _format_results(
    matches: list[tuple[str, int, str]],
    abs_dir: str,
    terms: list[str],
    case_sensitive: bool = False,
) -> dict[str, Any]:
    """Group *matches* by file, rank the files, and keep a few rows of each.

    A file is ranked by how many of *terms* it holds — a body hit and a title
    hit count the same here — then by what the file is: a note whose title
    carries the words, another note, an index, the activity log. The shortlist
    is what makes a question answerable: a word that appears in every note
    would otherwise put every note in the result."""
    grouped: dict[str, list[tuple[int, str]]] = {}
    for file_path, line_num, content in matches:
        rel = _relpath(file_path, abs_dir)
        grouped.setdefault(rel, []).append((line_num, content))

    ranked = []
    for rel, rows in grouped.items():
        title = _note_title(rel, abs_dir)
        title_hits = _title_hits(title, terms, case_sensitive)
        body = _fold(" ".join(content for _line, content in rows), case_sensitive)
        word_hits = sum(1 for term in terms if _fold(term, case_sensitive) in body)
        word_hits = max(word_hits, title_hits)
        ranked.append(
            (_file_group(rel, title_hits), -word_hits, -title_hits, rel, rows)
        )
    ranked.sort()

    results = []
    for _group, _negated_hits, _negated_title_hits, rel, rows in ranked[:MAX_FILES]:
        for line_num, content in sorted(rows)[:_ROWS_PER_FILE]:
            truncated, _ = truncate_text(content, 500, keep="head")
            results.append({"file": rel, "line": str(line_num), "content": truncated})

    by_title = sum(1 for entry in ranked if entry[0] == _TITLE_MATCH)
    summary = f"Found {len(matches)} matches in {len(grouped)} files."
    if by_title:
        summary += f" {by_title} of them about it by title."
    if len(results) < min(len(matches), _MAX_ROWS):
        summary += f" Showing {len(results)}."
    return {"summary": summary, "results": results}


def _relpath(file_path: str, abs_dir: str) -> str:
    return (
        os.path.relpath(file_path, abs_dir) if os.path.isabs(file_path) else file_path
    ).replace(os.sep, "/")


def _file_group(rel: str, title_hits: int) -> int:
    """Which band of the ranking *rel* belongs to."""
    if rel.startswith("activity-log/"):
        return _ACTIVITY
    if _is_index(rel):
        return _INDEX
    return _TITLE_MATCH if title_hits else _NOTE


def _is_index(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    try:
        configured = resolve_journal_index_name(CFG.LLM_JOURNAL_INDEX_FILE)
    except ValueError:
        configured = "index.md"
    return name in {"index.md", configured}


def _note_title(rel: str, abs_dir: str) -> str:
    """The `# ` title of a note, or "" for an index, the log, or no note."""
    if _is_index(rel) or rel.startswith("activity-log/"):
        return ""
    try:
        with open(os.path.join(abs_dir, rel), encoding="utf-8", errors="ignore") as f:
            return get_first_heading(f.read()) or ""
    except OSError:
        return ""


def _fold(text: str, case_sensitive: bool) -> str:
    """*text* under the same case rule the search matched with."""
    return text if case_sensitive else text.lower()


def _title_hits(title: str, terms: list[str], case_sensitive: bool = False) -> int:
    """How many of *terms* the title carries: it is what says "about this"."""
    folded = _fold(title, case_sensitive)
    if not folded:
        return 0
    return sum(1 for term in terms if _fold(term, case_sensitive) in folded)


def _no_matches(query: str, abs_dir: str) -> dict[str, Any]:
    empty: dict[str, Any] = {"summary": "No matches found.", "results": []}
    suggestions = _suggest_similar(query, abs_dir)
    if suggestions:
        empty["did_you_mean"] = suggestions
    return empty


def _suggest_similar(query: str, abs_dir: str) -> list[str]:
    """Note titles sharing a word with *query*, best first.

    Word overlap, not whole-string similarity. A question is longer than any
    title, so `difflib` scored a six-letter word against a ninety-character
    title at about 0.12 against its own 0.6 bar: the one mechanism meant to
    turn a dead end into a lead answered nothing, for every realistic query."""
    words = _significant_words(query)
    if not words:
        return []
    scored: list[tuple[int, str]] = []
    for category in NOTE_CATEGORIES:
        category_dir = os.path.join(abs_dir, category)
        if not os.path.isdir(category_dir):
            continue
        for filename in os.listdir(category_dir):
            if not filename.endswith(".md") or _is_index(f"{category}/{filename}"):
                continue
            try:
                # A note holding bytes that are not UTF-8 must not turn a
                # zero-hit search into a crash: suggesting titles is a courtesy,
                # and the search itself already reads these files leniently.
                with open(
                    os.path.join(category_dir, filename),
                    encoding="utf-8",
                    errors="ignore",
                ) as f:
                    heading = get_first_heading(f.read())
            except OSError:
                continue
            if not heading:
                continue
            haystack = f"{heading} {filename}".lower()
            hits = sum(1 for word in words if word in haystack)
            if hits:
                scored.append((-hits, heading))
    scored.sort()
    return [title for _negated_hits, title in scored[:5]]


def _significant_words(query: str) -> list[str]:
    """The words of *query* that could say what it is about."""
    words = re.findall(r"[a-z0-9][a-z0-9_-]+", query.lower())
    return [word for word in words if len(word) >= 3 and word not in _STOP_WORDS]
