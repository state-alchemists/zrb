import os
import re

from zrb.llm.tool.post_write_check import format_post_write_diagnostics

_READ_LINE_NUMBER = re.compile(r"^ *\d+\t")


async def replace_in_file(
    path: str,
    old_text: str,
    new_text: str,
    count: int = -1,
) -> str:
    """
    Replaces text in a file. Always Read the file first to get exact text.

    Read prefixes every line with its number (`cat -n` style: six columns, then
    a tab). That prefix is not in the file — strip it from old_text and
    new_text. Text copied straight out of Read is matched anyway, but only
    after the exact match has already failed.

    Falls back to fuzzy matching (whitespace-tolerant) if exact match fails.
    count=-1 replaces all occurrences; count=1 replaces only the first.

    The result must stay structurally valid — if the change would break indentation,
    imports, or syntax, widen old_text or use Write to rewrite the file instead.
    On success, runs LSP/static checks — errors appear as `[DIAGNOSTIC]` in the return value.
    """
    if old_text == "":
        # `"" in content` is always True, so an empty old_text would make
        # str.replace insert new_text between every character and corrupt the
        # file. Reject it outright — there is no sensible "replace nothing".
        return (
            f"Error: old_text is empty for {path}. "
            "[SYSTEM SUGGESTION]: old_text must be a non-empty snippet copied "
            "verbatim from the file. To create or fully overwrite a file, use "
            "Write instead."
        )
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        return (
            f"Error: File not found: {path}. "
            "[SYSTEM SUGGESTION]: Check the path, or use Write to create the "
            "file if it should not exist yet."
        )

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return (
            f"Error: Cannot read file {path}: {e}. "
            "[SYSTEM SUGGESTION]: Verify the path and your read permissions, "
            "then retry."
        )

    # Exact match
    actual_old = old_text if old_text in content else None
    fuzzy_note = ""

    # Fuzzy fallback
    if actual_old is None:
        matched = _find_fuzzy_match(content, old_text)
        if matched is not None:
            actual_old = matched
            fuzzy_note = " (fuzzy match: whitespace differences were normalized)"

    # Last resort: old_text copied verbatim out of Read's numbered output.
    if actual_old is None:
        stripped_old = _strip_read_line_numbers(old_text)
        if stripped_old is not None:
            actual_old = (
                stripped_old
                if stripped_old in content
                else _find_fuzzy_match(content, stripped_old)
            )
            if actual_old is not None:
                old_text = stripped_old
                new_text = _strip_prefix_per_line(new_text)
                fuzzy_note = " (stripped Read's line-number prefix from old_text)"

    if actual_old is None:
        lines = content.splitlines()
        # Compare on the un-prefixed text: with the prefix still attached, the
        # first line matches nothing and this whole hint goes silent exactly
        # when it is most useful.
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
                    f"Error: '{_trunc(old_text, 80)}' not found in {path}.\n"
                    f"Similar lines found:\n{preview}\n"
                    f"[SYSTEM SUGGESTION]: old_text must match the file exactly. "
                    f"Check for trailing spaces or indentation differences. "
                    f"The lines above are shown as the file holds them — copy "
                    f"from those, without Read's line-number prefix."
                )
        return (
            f"Error: '{_trunc(old_text, 80)}' not found in {path}.\n"
            f"[SYSTEM SUGGESTION]: Re-Read the region and copy old_text from it, "
            f"dropping the line-number prefix through the first tab. Do not "
            f"retry with guessed text."
        )

    match_count = content.count(actual_old)
    new_content = content.replace(actual_old, new_text, count)

    # A no-op reached this far means old_text *was* found, so it is never the
    # "not found" case above — and each of its three causes needs different
    # advice. Retrying is futile in all three, and models do retry a bare
    # status, so each says which one it is instead of hedging between them.
    if content == new_content:
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
        # old_text differs from new_text, yet the matched region equals it, so
        # the match was fuzzy: the file already reads as new_text and only
        # whitespace told old_text apart from it.
        return (
            f"No changes made to {path}: the matched region already reads "
            "exactly as new_text, so this edit is already applied — only "
            "whitespace told old_text apart from it. "
            "[SYSTEM SUGGESTION]: Do not repeat this call — it will keep "
            "returning this. Read the file to confirm its current state, then "
            "move on or edit a different region."
        )

    try:
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        return (
            f"Error: Cannot write file {path}: {e}. "
            "[SYSTEM SUGGESTION]: Verify the path and your write permissions, "
            "then retry."
        )

    replacements = match_count if count == -1 else min(match_count, count)
    diag_suffix = await format_post_write_diagnostics(abs_path)
    return (
        f"Successfully updated {path} ({replacements} replacement(s)){fuzzy_note}"
        f"{diag_suffix}"
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
        return None  # Single-line indent shifts are too ambiguous to fuzzy-match

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
    """Undo ``Read``'s ``cat -n`` prefix when it was copied into an edit argument.

    ``Read`` numbers every line, so text copied straight out of its output
    cannot match the file. That is the likeliest reason an otherwise-verbatim
    ``old_text`` fails, and it is invisible in the model's own transcript: the
    prefix looks like the leading whitespace of the line it precedes.

    Returns ``None`` unless *every* line carries the prefix, so a partial copy
    is never silently mangled. Callers reach this only after an exact and a
    fuzzy match have both failed, so a file that genuinely contains ``cat -n``
    text — a fixture, a pasted diff — still edits through the exact path.
    """
    lines = text.splitlines(keepends=True)
    if not lines or not all(_READ_LINE_NUMBER.match(line) for line in lines):
        return None
    return _strip_prefix_per_line(text)


def _strip_prefix_per_line(text: str) -> str:
    """Drop ``Read``'s prefix from whichever lines carry it, leaving the rest.

    The all-or-nothing rule in ``_strip_read_line_numbers`` is right for
    ``old_text``: a partial match there means the guess was wrong, and mangling
    it would edit the wrong region. For ``new_text`` the same rule inverts into
    data loss. We only reach this function once ``old_text`` has *proved* the
    model was copying out of ``Read``, and the usual edit changes one line — so
    the replacement arrives with prefixes on the lines that were copied and none
    on the line that was rewritten. All-or-nothing then declines to strip and
    writes ``     3\\tsome text`` into the file, reported as a success. On a
    ``.py`` file the post-write diagnostics catch it; on markdown or YAML
    nothing does.

    Per-line is safe here for the same reason the caller is: a file that
    genuinely contains ``cat -n`` text matched on the exact path and never got
    this far.
    """
    return "".join(
        _READ_LINE_NUMBER.sub("", line, count=1)
        for line in text.splitlines(keepends=True)
    )


def _find_fuzzy_match(content: str, old_text: str) -> str | None:
    """Try relaxed matching strategies in order. Returns the actual content substring or None."""
    for strategy in (_match_line_trimmed, _match_indentation_flexible):
        result = strategy(content, old_text)
        if result is not None:
            return result
    return None


def _trunc(s: str, n: int) -> str:
    return (s[:n] + "...") if len(s) > n else s
