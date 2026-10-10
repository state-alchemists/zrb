import json
import os
import re
import shutil
import subprocess
from typing import Annotated, Any

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.tool.journal_write import NOTE_CATEGORIES
from zrb.util.markdown import get_first_heading
from zrb.util.string.suggestion import suggest_name
from zrb.util.truncate import truncate_text


def search_journal(
    query: Annotated[str, Field(description="Regex pattern to search for.")],
    case_sensitive: Annotated[
        bool, Field(description="False (default): case-insensitive search.")
    ] = False,
) -> dict[str, Any]:
    """
    Searches the journal for a regex pattern.

    Returns matching lines with file names and line numbers. A zero-hit search
    suggests nearby note titles under `did_you_mean` — and is not proof the
    topic was never recorded: try those titles or a synonym before concluding.

    Call this before WriteJournalNote or DeleteJournalNote whenever you are
    not certain a slug is free, or that it names the note you intend to touch.
    Wait for this result before issuing that write or delete — don't batch
    the two calls, since the write/delete it should inform depends on what
    this search finds.
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

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query, flags)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {e}"}

    if shutil.which("rg"):
        return _search_with_rg(query, abs_dir, case_sensitive)
    return _search_with_python(query, abs_dir, pattern)


search_journal.__name__ = "SearchJournal"


def _search_with_rg(query: str, abs_dir: str, case_sensitive: bool) -> dict[str, Any]:
    cmd = ["rg", "--json", "--no-messages"]
    if not case_sensitive:
        cmd.append("--ignore-case")
    cmd.extend(["--", query, abs_dir])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"error": f"rg failed: {e}"}

    if proc.returncode == 2:
        return {"error": f"rg error: {proc.stderr.strip()}"}

    return _format_results(_parse_rg_json(proc.stdout), abs_dir, query)


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


def _search_with_python(
    query: str, abs_dir: str, pattern: re.Pattern
) -> dict[str, Any]:
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
                            rel = os.path.relpath(file_path, abs_dir)
                            raw_lines.append((rel, line_num, line.rstrip()))
            except OSError:
                pass
    return _format_results(raw_lines, abs_dir, query)


def _format_results(
    matches: list[tuple[str, int, str]], abs_dir: str, query: str
) -> dict[str, Any]:
    results = []
    for file_path, line_num, content in matches:
        rel = (
            os.path.relpath(file_path, abs_dir)
            if os.path.isabs(file_path)
            else file_path
        )
        truncated, _ = truncate_text(content, 500, keep="head")
        results.append({"file": rel, "line": str(line_num), "content": truncated})

    if not results:
        empty: dict[str, Any] = {"summary": "No matches found.", "results": []}
        suggestions = _suggest_similar(query, abs_dir)
        if suggestions:
            empty["did_you_mean"] = suggestions
        return empty

    return {"summary": f"Found {len(results)} matches.", "results": results}


def _suggest_similar(query: str, abs_dir: str) -> list[str]:
    """Fuzzy-match *query* against note titles in the category directories,
    so a zero-hit search doesn't read as "never documented"."""
    candidates: list[str] = []
    for name in NOTE_CATEGORIES:
        category_dir = os.path.join(abs_dir, name)
        if not os.path.isdir(category_dir):
            continue
        for filename in os.listdir(category_dir):
            if not filename.endswith(".md") or filename == "index.md":
                continue
            try:
                with open(os.path.join(category_dir, filename), encoding="utf-8") as f:
                    heading = get_first_heading(f.read())
                if heading:
                    candidates.append(heading)
            except OSError:
                continue
    return suggest_name(query, candidates, limit=5)
