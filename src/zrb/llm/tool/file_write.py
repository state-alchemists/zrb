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
from zrb.llm.tool.post_write_check import (
    compose_write_result,
    format_post_write_diagnostics,
)


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
    Creates a file, replaces one, or appends to one. Use Edit to change part
    of an existing file — rewriting a file you have not just read drops
    everything you did not reproduce, and nothing reports that loss.

    An existing file whose bytes aren't valid UTF-8 (a binary) is refused in
    every mode — this tool writes UTF-8 text only and would corrupt it.

    LSP/static checks run after the write. When they find errors, the result
    opens with `FAILED` and a `[DIAGNOSTIC]` list: the bytes did reach disk,
    so do not re-send them. Read the file and make a targeted fix — the
    requested change is not complete until those errors are gone.
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
        # Append still refuses binaries, but needs no prior observation.
        blocked = check_writable_text(abs_path)
        if blocked is not None:
            return blocked

    parent = os.path.dirname(abs_path)
    # Reported (not refused) so a path resolved against the wrong base is noticed.
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

    # Best-effort; the hash must cover the file's full new state.
    try:
        if mode == "w":
            record_observed(abs_path, content)
        else:
            with open(abs_path, "r", encoding="utf-8") as f:
                record_observed(abs_path, f.read())
    except Exception as e:
        CFG.LOGGER.debug(f"Failed to record observed content for {abs_path}: {e}")

    dir_note = f" (created new directory {parent})" if created_dir else ""
    return compose_write_result(
        f"Successfully wrote to {path}{dir_note}",
        await format_post_write_diagnostics(abs_path),
    )
