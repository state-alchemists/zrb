import os
from typing import Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.tool.file_observation import (
    check_observed,
    check_writable_text,
    path_write_lock,
    record_observed,
)
from zrb.llm.tool.post_write_check import format_post_write_diagnostics


async def write_file(
    path: Annotated[
        str,
        Field(description="File to write, creating it and any missing parent dirs."),
    ],
    content: Annotated[str, Field(description="Full text to write, UTF-8.")],
    mode: Annotated[
        str,
        Field(
            description=(
                '"w" (default) overwrites the whole file — refused against an '
                "existing file this session hasn't Read/Written/Edited yet. "
                '"a" appends, for writing large content in chunks.'
            )
        ),
    ] = "w",
) -> str:
    """
    Writes or appends to a file, creating it and any missing parent directories.

    For large content, write in chunks: first with mode="w", subsequent with mode="a".
    An existing file whose bytes aren't valid UTF-8 (a binary) is refused in
    every mode — this tool writes UTF-8 text only and would corrupt it.
    On success, runs LSP/static checks — errors appear as `[DIAGNOSTIC]` in the return value.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    async with path_write_lock(abs_path):
        return await _write_file_locked(path, abs_path, content, mode)


async def _write_file_locked(path: str, abs_path: str, content: str, mode: str) -> str:
    existed_before = os.path.exists(abs_path)
    if mode == "w" and existed_before:
        # Includes the binary refusal: it precedes the observed-state check.
        blocked = check_observed(abs_path)
        if blocked is not None:
            return blocked
    elif existed_before:
        # Append corrupts a binary just as surely as an overwrite would —
        # same refusal, no observed-state requirement (nothing is destroyed).
        blocked = check_writable_text(abs_path)
        if blocked is not None:
            return blocked

    parent = os.path.dirname(abs_path)
    # Sampled before makedirs. Creating a directory is a change to the user's
    # tree, and a silent one reads as "the path already existed" — which is how a
    # path resolved against the wrong base lands a file where nothing reads it.
    # Reported, not refused: writing a new tree is often exactly the intent.
    created_dir = bool(parent) and not os.path.isdir(parent)
    try:
        os.makedirs(parent, exist_ok=True)
        with open(abs_path, mode, encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return (
            f"Error writing to file {path}: {e}. "
            "[SYSTEM SUGGESTION]: Check that the parent path is a directory (not a "
            "file), that you have write permission, and that there is free disk "
            "space, then retry."
        )

    # Best-effort: the write already succeeded above, so a hiccup here must
    # not turn that success into a reported error. mode="w" already wrote
    # exactly `content` as the file's full new state, so it's recorded
    # directly; mode="a" only wrote a suffix, so the file is re-read instead
    # — the recorded hash must reflect the true, full new state, or a later
    # mode="w" in the same session would see a mismatch against its own
    # prior appends.
    try:
        if mode == "w":
            record_observed(abs_path, content)
        else:
            with open(abs_path, "r", encoding="utf-8") as f:
                record_observed(abs_path, f.read())
    except Exception as e:
        CFG.LOGGER.debug(f"Failed to record observed content for {abs_path}: {e}")

    dir_note = f" (created new directory {parent})" if created_dir else ""
    suffix = await format_post_write_diagnostics(abs_path)
    return f"Successfully wrote to {path}{dir_note}{suffix}"
