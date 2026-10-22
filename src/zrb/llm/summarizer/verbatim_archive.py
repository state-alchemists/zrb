"""Append-only, human-readable archive of the messages a summary replaces.

Compaction is lossy by design: the model gets a summary, and the history
manager writes the compacted list over the session file, so the original text
is gone unless something kept it. This module is that something.

The archive lives beside the history files, under
``<LLM_HISTORY_DIR>/verbatim/``, one markdown file per conversation. Each
compaction appends a section; nothing is ever rewritten or removed, so a later
compaction cannot lose an earlier one. The summary names the file, so the agent
can read back what the summary left out.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.history_manager.file_history_manager import safe_segment
from zrb.llm.summarizer.message_converter import message_to_text

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage

ARCHIVE_DIR_NAME = "verbatim"
"""Subdirectory of `LLM_HISTORY_DIR` holding the archives."""


def verbatim_archive_path(session_name: str, history_dir: str | None = None) -> str:
    """The archive file for *session_name*.

    `history_dir` is the directory the history manager stores conversations in,
    so the archive follows the same storage configuration; it defaults to
    `CFG.LLM_HISTORY_DIR` (``~/.zrb/llm-history``). The path is absolute: it is
    handed to the model, which reads what its working directory would otherwise
    make ambiguous.
    """
    base = os.path.expanduser(history_dir or CFG.LLM_HISTORY_DIR)
    return os.path.abspath(
        os.path.join(base, ARCHIVE_DIR_NAME, f"{safe_segment(session_name)}.md")
    )


def conversation_key(opening_text: str) -> str:
    """A stable archive name derived from a conversation's opening message.

    The fallback when the caller cannot name the conversation: a rename or a
    resume does not change it, and two conversations that open differently do
    not share a file. The readable prefix makes the file findable; the digest
    keeps two similar openings apart.
    """
    readable = " ".join(opening_text.split())[:48].strip() or "conversation"
    digest = hashlib.sha1(opening_text.encode("utf-8")).hexdigest()[:8]
    return f"{safe_segment(readable)}-{digest}"


def archive_verbatim_history(
    messages: "list[ModelMessage]",
    *,
    path: str,
    tokens: int | None = None,
) -> str | None:
    """Append *messages* to the archive at *path*; return the path when written.

    Never raises: failing to archive must not fail the turn that needed the
    summary. ``None`` means nothing was written (no messages, write failure).
    """
    if not messages:
        return None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        is_new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as stream:
            if is_new:
                stream.write(_file_header(os.path.basename(path)[: -len(".md")]))
            stream.write(_render_section(messages, tokens))
        return path
    except OSError as e:
        CFG.LOGGER.warning(f"Could not archive verbatim history at {path}: {e}")
        return None


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
