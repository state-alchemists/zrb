"""Append-only, human-readable archive of the messages a summary replaces.

Compaction is lossy by design: the model gets a summary, and the history
manager writes the compacted list over the session file, so the original text
is gone unless something kept it. This module is that something.

The archive lives beside the history files, under
``<LLM_HISTORY_DIR>/verbatim/``, one markdown file per conversation. Each
compaction appends a section; nothing is ever rewritten or removed, so a later
compaction cannot lose an earlier one. A written section is named in the
summary, so the agent can read back what the summary left out. A failed append
is cut back to the size it started at and returns ``None``, so the summary
carries no pointer to a partial record.

A transcript is private: on POSIX the directory is created ``0700`` and the file
``0600``, and neither is written through a symlink. Windows has neither mode
bits nor an equivalent open flag, so there the archive inherits the profile
directory's permissions.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.history_manager.archive_layout import (
    ARCHIVE_DIR_NAME,
    archive_lock_path,
    conversation_key,
    verbatim_archive_path,
)
from zrb.llm.summarizer.message_converter import message_to_text
from zrb.util.file_lock import FileLockTimeout, hold_file_lock
from zrb.util.owner_only import makedirs_owner_only, tighten_once

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage

__all__ = [
    "ARCHIVE_DIR_NAME",
    "archive_lock_path",
    "archive_verbatim_history",
    "conversation_key",
    "verbatim_archive_path",
]

# Narrowed again after creation, in `_make_owner_only`: a umask that clears one
# of these bits would otherwise leave the archive readable by others.
_ARCHIVE_FILE_MODE = 0o600

# `O_APPEND` is the append-only promise: the kernel puts every write at the end,
# so two writers interleave sections instead of overwriting each other's.
# `O_NOFOLLOW` refuses a symlink standing where the archive belongs; Windows has
# no such flag, and creating a symlink there needs a privilege the caller of a
# hijack would not have.
_APPEND_FLAGS = (
    os.O_WRONLY
    | os.O_CREAT
    | os.O_APPEND
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_BINARY", 0)
)


def archive_verbatim_history(
    messages: "list[ModelMessage]",
    *,
    path: str,
    tokens: int | None = None,
) -> str | None:
    """Append *messages* to the archive at *path*; return the path when written.

    Never raises: failing to archive must not fail the turn that needed the
    summary. ``None`` means nothing was written (no messages, write failure).
    `tokens` is the size of *messages* as given, so a section's message count and
    its token count describe the same list — the caller drops anything it does
    not archive (prior summaries) before counting.

    The archive is private and symlink-proof on POSIX: the file is created
    ``0600`` inside a ``0700`` directory and opened ``O_NOFOLLOW``, so a link
    planted at either path cannot redirect the append to a file of the planter's
    choosing. A write that fails partway is cut back to its pre-write length, so
    no half-written section survives; on the ``None`` that follows, a caller must
    never point at the archive.
    """
    if not messages:
        return None
    # Rendered before the file is touched: a message that cannot be rendered
    # must not leave a header-only archive behind. Its own try/except, not
    # folded into the one below: an unexpected message shape is this
    # function's to swallow too, not only the I/O that follows it -- letting
    # it escape broke the "never raises" contract and took the whole
    # compaction down with it (summarize_history's own broad handler discards
    # the replacement summary and returns the original history unchanged).
    try:
        body = _render_section(messages, tokens)
    except Exception as e:
        CFG.LOGGER.warning(f"Could not render verbatim history for {path}: {e}")
        return None
    try:
        # The lock makes the rollback exact: no other appender's section can land
        # between the size read and the truncate that undoes a failed write. The
        # directory has to exist before the lock file can sit in it.
        _ensure_archive_directory(os.path.dirname(path))
        # No owned_entries restriction: unlike the journal root, "verbatim" is
        # never user-configured directly -- zrb names and creates it itself
        # beneath whatever LLM_HISTORY_DIR is, and only ever puts its own
        # archives and lock sidecars there, so narrowing the whole
        # subdirectory cannot reach content that belongs to something else.
        tighten_once(os.path.dirname(path))
        with hold_file_lock(
            archive_lock_path(path), timeout=CFG.LLM_ARCHIVE_LOCK_TIMEOUT
        ):
            _append_new_section(path, body)
    except FileLockTimeout:
        CFG.LOGGER.warning(
            f"No verbatim archive at {path}: another writer held its lock for "
            f"{CFG.LLM_ARCHIVE_LOCK_TIMEOUT}s (LLM_ARCHIVE_LOCK_TIMEOUT). This "
            "summary therefore carries no archive pointer, and the text it "
            "replaced survives only in that summary."
        )
        return None
    except OSError as e:
        CFG.LOGGER.warning(f"Could not archive verbatim history at {path}: {e}")
        return None
    return path


def _append_new_section(path: str, body: str) -> None:
    """Append *body* under the held lock, with the file header if it is empty."""
    descriptor, size_before = _open_archive(path)
    # Zero bytes means created here, or an earlier attempt rolled back to
    # nothing: either way this section is the first one the file will hold.
    header = "" if size_before else _file_header(os.path.basename(path)[: -len(".md")])
    _append_section(descriptor, size_before, header + body)


def _open_archive(path: str) -> "tuple[int, int]":
    """Open the archive for appending; return its descriptor and current size.

    The caller has already made the directory owner-only. A symlink standing
    where the file belongs is refused rather than followed, through `O_NOFOLLOW`,
    which only POSIX has.
    """
    descriptor = os.open(path, _APPEND_FLAGS, _ARCHIVE_FILE_MODE)
    try:
        size_before = os.fstat(descriptor).st_size
        if size_before == 0:
            _make_owner_only(descriptor)
    except OSError:
        _close_quietly(descriptor)
        raise
    return descriptor, size_before


def _ensure_archive_directory(directory: str) -> None:
    """Create *directory* owner-only; refuse another user's directory.

    Raises `OSError` (`PermissionError` for the refusals) so a failed write is
    reported instead of appending into whatever the path points at. A directory
    that already exists keeps the mode it has: it may predate this rule, and
    changing a directory zrb does not exclusively own is not this call's to do.

    `makedirs_owner_only` already refuses a symlink anywhere from *directory*
    up to its nearest existing ancestor (including one planted in the race
    between its own check and the `mkdir` that follows), and creates every
    missing level at the right mode instead of `os.makedirs()`'s mode
    argument, which only ever reaches the leaf. Ownership is the one check
    specific to the archive: a *directory* that already exists, is a real
    directory, and is not a symlink can still belong to someone else.
    """
    makedirs_owner_only(directory)
    info = os.lstat(directory)
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise PermissionError(
            f"Archive directory is not owned by the current user: {directory}"
        )


def _make_owner_only(descriptor: int) -> None:
    """Narrow a file this call created to ``0600``, whatever the umask.

    Only for a file created here: a mode left on an existing archive — one
    written before this rule, say — is not this call's to change. Windows has no
    `fchmod`, and its permission bits would not express ``0600`` anyway.
    """
    if hasattr(os, "fchmod"):
        os.fchmod(descriptor, _ARCHIVE_FILE_MODE)


def _append_section(descriptor: int, size_before: int, text: str) -> None:
    """Append *text*; cut the file back to *size_before* when the write fails.

    Everything past *size_before* is this call's own bytes, so truncating
    removes exactly what a failed write left behind without reading the archive
    into memory. A concurrent appender's section that landed in the same window
    goes too: two zrb processes on one archive are the residual risk.
    """
    try:
        # `closefd=False`: the descriptor must outlive a flush that fails on
        # close, so the rollback below still has a file to cut back.
        with os.fdopen(descriptor, "a", encoding="utf-8", closefd=False) as stream:
            stream.write(text)
    except OSError:
        _cut_back(descriptor, size_before)
        raise
    finally:
        _close_quietly(descriptor)


def _cut_back(descriptor: int, size_before: int) -> None:
    """Truncate the open archive back to *size_before*; best effort.

    When this fails too the partial section stays on disk. It is logged, not
    repaired: repairing it means rewriting a file whose whole promise is that it
    is only ever appended to.
    """
    try:
        os.ftruncate(descriptor, size_before)
    except OSError as e:
        CFG.LOGGER.warning(f"Could not roll back a partial archive write: {e}")


def _close_quietly(descriptor: int) -> None:
    """Close *descriptor*, swallowing an error: there is nothing left to repair.

    The bytes were flushed by the stream's own close, and the module's contract
    is never to raise, so a failure at this last step is dropped rather than
    turned into an exception.
    """
    try:
        os.close(descriptor)
    except OSError:
        pass


def _file_header(session_name: str) -> str:
    return (
        f"# Verbatim history — {session_name}\n"
        "\n"
        "Every message a compaction replaced with a summary, word for word.\n"
        "Append-only: a later compaction adds a section below; nothing here is\n"
        "rewritten or removed. Attachment bytes are named, not copied. Read this\n"
        "file when a summary lacks the detail you need.\n"
        "\n"
    )


def _render_section(messages: "list[ModelMessage]", tokens: int | None) -> str:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    size = f", ~{tokens:,} tokens" if tokens is not None else ""
    lines = [f"## Compacted {stamp} — {len(messages)} message(s){size}", ""]
    for index, message in enumerate(messages, 1):
        lines.append(f"### {index}. {_role_label(message)}")
        lines.append("")
        lines.append(message_to_text(message).rstrip() or "[empty message]")
        note = _non_text_note(message)
        if note:
            lines.append("")
            lines.append(note)
        lines.append("")
    return "\n".join(lines)


def _non_text_note(message: object) -> str:
    """Say that a message's attachment bytes are not in the archive.

    The rendering names an attachment but cannot carry its bytes; saying so
    keeps the archive's promise ("word for word") honest.
    """
    parts = getattr(message, "parts", None) or []
    has_binary = any(_has_binary_content(part) for part in parts)
    if has_binary:
        return "[attachment content is named here, not copied into this archive]"
    return ""


def _has_binary_content(part: object) -> bool:
    """Whether a part carries attachment bytes, directly or in its content list."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import FilePart

    def is_binary(item: object) -> bool:
        return isinstance(item, FilePart) or isinstance(
            getattr(item, "data", None), bytes
        )

    if is_binary(part):
        return True
    content = getattr(part, "content", None)
    if isinstance(content, (list, tuple)):
        return any(is_binary(item) for item in content)
    return False


def _role_label(message: object) -> str:
    """Who spoke: `User`, `Tool result`, `Assistant`, or the type name."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest, ModelResponse, ToolReturnPart
    from zrb.llm.agent.types import UserPromptPart

    if isinstance(message, ModelRequest):
        parts = getattr(message, "parts", [])
        if any(isinstance(part, UserPromptPart) for part in parts):
            return "User"
        if any(isinstance(part, ToolReturnPart) for part in parts):
            return "Tool result"
        return "Request"
    if isinstance(message, ModelResponse):
        return "Assistant"
    return type(message).__name__
