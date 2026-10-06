import os
import re
from typing import Annotated

from pydantic import Field

from zrb.llm.tool.file_observation import path_write_lock, record_observed
from zrb.llm.tool.post_write_check import (
    compose_write_result,
    format_post_write_diagnostics,
)
from zrb.util.truncate import truncate_display

_READ_LINE_NUMBER = re.compile(r"^ *\d+\t")


async def replace_in_file(
    path: Annotated[str, Field(description="File to edit.")],
    old_text: Annotated[
        str,
        Field(
            description=(
                "Exact text to replace, copied verbatim from Read (strip its "
                "line-number prefix first). Falls back to whitespace-tolerant "
                "fuzzy matching if the exact text isn't found."
            )
        ),
    ],
    new_text: Annotated[str, Field(description="Text to replace old_text with.")],
    count: Annotated[
        int,
        Field(
            description=(
                "How many occurrences to replace. The default -1 replaces "
                "EVERY occurrence in the file. Pass count=1 unless you have "
                "read the file and confirmed old_text appears exactly once, "
                "or you actually intend a file-wide replacement."
            )
        ),
    ] = -1,
) -> str:
    """
    Replaces text in a file. Always Read the file first to get exact text.

    Read prefixes every line with its number (`cat -n` style: six columns, then
    a tab). That prefix is not in the file — strip it from old_text and
    new_text. Text copied straight out of Read is matched anyway, but only
    after the exact match has already failed.

    Read the result, not just its status. It reports how many replacements
    happened, and says so when old_text matched only after whitespace was
    normalized — a fuzzy match can land on a block at a different indentation
    level. If either is not what you expected, Read the file before doing
    anything else.

    Keep the result structurally valid — if the change would break indentation,
    imports, or syntax, widen old_text or use Write to rewrite the file instead.
    LSP/static checks run after the write. When they find errors, the result
    opens with `FAILED` and a `[DIAGNOSTIC]` list: the replacement did reach
    disk, so do not re-issue it. Read the file and make a targeted fix — the
    requested change is not complete until those errors are gone.
    """
    if old_text == "":
        # str.replace("", x) would insert x between every character.
        return (
            f"Error: old_text is empty for {path}. "
            "[SYSTEM SUGGESTION]: old_text must be a non-empty snippet copied "
            "verbatim from the file. To create or fully overwrite a file, use "
            "Write instead."
        )
    abs_path = os.path.abspath(os.path.expanduser(path))
    async with path_write_lock(abs_path):
        return await _replace_in_file_locked(path, abs_path, old_text, new_text, count)


async def _replace_in_file_locked(
    path: str,
    abs_path: str,
    old_text: str,
    new_text: str,
    count: int,
) -> str:
    missing = _describe_missing_file(path, abs_path)
    if missing is not None:
        return missing

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return (
            f"Error: Cannot read file {path}: {e}. "
            "[SYSTEM SUGGESTION]: Verify the path and your read permissions, "
            "then retry."
        )

    actual_old, old_text, new_text, fuzzy_note = _locate_match(
        content, old_text, new_text
    )
    if actual_old is None:
        return _describe_missing_match(content, old_text, path)

    match_count = content.count(actual_old)
    new_content = content.replace(actual_old, new_text, count)

    if content == new_content:
        return _describe_noop(path, old_text, new_text, count)

    try:
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        return (
            f"Error: Cannot write file {path}: {e}. "
            "[SYSTEM SUGGESTION]: Verify the path and your write permissions, "
            "then retry."
        )
    record_observed(abs_path, new_content)

    replacements = match_count if count == -1 else min(match_count, count)
    return compose_write_result(
        f"Successfully updated {path} ({replacements} replacement(s)){fuzzy_note}",
        await format_post_write_diagnostics(abs_path),
    )


def _describe_missing_file(path: str, abs_path: str) -> str | None:
    """Explain an unreadable path, or return None when the file exists."""
    if os.path.exists(abs_path):
        return None
    parent = os.path.dirname(abs_path)
    if parent and not os.path.isdir(parent):
        # A missing directory means a wrong base path; suggesting Write would
        # create a new tree where nothing reads it.
        return (
            f"Error: File not found: {path} — its directory does not exist "
            f"either ({parent}). "
            "[SYSTEM SUGGESTION]: This is a wrong path, not a missing file. "
            "Re-resolve it against the working directory in System Context. "
            "Do not Write to it: that would create the directory and leave "
            "the file where nothing reads it."
        )
    return (
        f"Error: File not found: {path}. "
        "[SYSTEM SUGGESTION]: Check the path, or use Write to create the "
        "file if it should not exist yet."
    )


def _locate_match(
    content: str, old_text: str, new_text: str
) -> tuple[str | None, str, str, str]:
    """Locate `old_text`: exact, then fuzzy, then with Read's line prefix stripped.

    Returns `(actual_old, old_text, new_text, note)`; `actual_old` is None when
    nothing matched. The prefix-strip strategy rewrites `old_text`/`new_text`.
    """
    if old_text in content:
        return old_text, old_text, new_text, ""

    matched = find_fuzzy_match(content, old_text)
    if matched is not None:
        return (
            matched,
            old_text,
            new_text,
            " — fuzzy match: old_text matched only after whitespace was "
            "normalized, so new_text was written with the indentation you "
            "supplied, not the file's. Read the edited region and confirm the "
            "indentation is correct before moving on.",
        )

    stripped_old = _strip_read_line_numbers(old_text)
    if stripped_old is not None:
        matched = (
            stripped_old
            if stripped_old in content
            else find_fuzzy_match(content, stripped_old)
        )
        if matched is not None:
            return (
                matched,
                stripped_old,
                _strip_prefix_per_line(new_text),
                " (stripped Read's line-number prefix from old_text)",
            )

    return None, old_text, new_text, ""


def _describe_missing_match(content: str, old_text: str, path: str) -> str:
    """Explain a failed match, pointing at near-misses when there are any."""
    lines = content.splitlines()
    old_lines = (_strip_read_line_numbers(old_text) or old_text).splitlines()
    if old_lines:
        first_line = old_lines[0]
        near_matches = [
            (i + 1, line) for i, line in enumerate(lines) if first_line in line
        ]
        if near_matches:
            preview = "\n".join(
                f"  Line {num}: {line[:120]}" for num, line in near_matches[:3]
            )
            return (
                f"Error: '{truncate_display(old_text, 80)}' not found in {path}.\n"
                f"Similar lines found:\n{preview}\n"
                f"[SYSTEM SUGGESTION]: old_text must match the file exactly. "
                f"Check for trailing spaces or indentation differences. "
                f"The lines above are shown as the file holds them — copy "
                f"from those, without Read's line-number prefix."
            )
    return (
        f"Error: '{truncate_display(old_text, 80)}' not found in {path}.\n"
        f"[SYSTEM SUGGESTION]: Re-Read the region and copy old_text from it, "
        f"dropping the line-number prefix through the first tab. Do not "
        f"retry with guessed text."
    )


def _describe_noop(path: str, old_text: str, new_text: str, count: int) -> str:
    """Explain which of three causes made a located match change nothing."""
    if old_text == new_text:
        return (
            f"No changes made to {path}: old_text and new_text are "
            "identical, so this call cannot change the file. "
            "[SYSTEM SUGGESTION]: Do not repeat this call — it will keep "
            "returning this. Re-issue it with a new_text that differs from "
            "old_text, or, if the file already holds the intended content, "
            "move on to the next step."
        )
    if count == 0:
        return (
            f"No changes made to {path}: count=0 asks for zero "
            "replacements. "
            "[SYSTEM SUGGESTION]: Do not repeat this call as-is. Omit "
            "count to replace every occurrence, or pass count=1 to replace "
            "only the first."
        )
    # A fuzzy match whose region already equals new_text.
    return (
        f"No changes made to {path}: the matched region already reads "
        "exactly as new_text, so this edit is already applied — only "
        "whitespace told old_text apart from it. "
        "[SYSTEM SUGGESTION]: Do not repeat this call — it will keep "
        "returning this. Read the file to confirm its current state, then "
        "move on or edit a different region."
    )


def _match_line_trimmed(content: str, old_text: str) -> str | None:
    """Return actual content substring matching old_text after stripping trailing whitespace per line."""
    old_lines = old_text.splitlines()
    if not old_lines:
        return None
    old_stripped = [line.rstrip() for line in old_lines]
    content_lines = content.splitlines(keepends=True)
    n = len(old_lines)
    for i in range(len(content_lines) - n + 1):
        block = content_lines[i : i + n]
        if [line.rstrip() for line in block] == old_stripped:
            return "".join(block)
    return None


def _match_indentation_flexible(content: str, old_text: str) -> str | None:
    """Return actual content substring matching old_text after removing common indentation."""
    old_lines = old_text.splitlines()
    if len(old_lines) < 2:
        return None  # single-line indent shifts are too ambiguous

    def _min_indent(lines: list[str]) -> int:
        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            return 0
        return min(len(line) - len(line.lstrip()) for line in non_empty)

    old_dedented = [line[_min_indent(old_lines) :] for line in old_lines]
    content_lines = content.splitlines(keepends=True)
    n = len(old_lines)
    for i in range(len(content_lines) - n + 1):
        block = content_lines[i : i + n]
        block_clean = [line.rstrip("\n").rstrip("\r") for line in block]
        shift = _min_indent(block_clean)
        if [line[shift:] for line in block_clean] == old_dedented:
            return "".join(block)
    return None


def _strip_read_line_numbers(text: str) -> str | None:
    """Undo ``Read``'s ``cat -n`` prefix, or ``None`` unless every line carries it."""
    lines = text.splitlines(keepends=True)
    if not lines or not all(_READ_LINE_NUMBER.match(line) for line in lines):
        return None
    return _strip_prefix_per_line(text)


def _strip_prefix_per_line(text: str) -> str:
    """Drop ``Read``'s prefix from whichever lines carry it.

    Per-line (not all-or-nothing) for ``new_text``: a rewritten line has no
    prefix while the copied ones do.
    """
    return "".join(
        _READ_LINE_NUMBER.sub("", line, count=1)
        for line in text.splitlines(keepends=True)
    )


def find_fuzzy_match(content: str, old_text: str) -> str | None:
    """Try relaxed matching strategies in order. Returns the actual content substring or None."""
    for strategy in (_match_line_trimmed, _match_indentation_flexible):
        result = strategy(content, old_text)
        if result is not None:
            return result
    return None
