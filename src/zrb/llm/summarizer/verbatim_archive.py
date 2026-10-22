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

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.history_manager.file_history_manager import safe_segment
from zrb.llm.summarizer.message_converter import message_to_text

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage

ARCHIVE_DIR_NAME = "verbatim"
"""Subdirectory of `LLM_HISTORY_DIR` holding the archives."""


def verbatim_archive_path(session_name: str, history_dir: str | None = None) -> str:
    """The archive file for *session_name*.

    `history_dir` defaults to `CFG.LLM_HISTORY_DIR`, so the archive follows the
    configured history location (``~/.zrb/llm-history`` by default) and moves
    with it. The path is absolute: it is handed to the model, which reads what
    its working directory would otherwise make ambiguous.
    """
    base = os.path.expanduser(history_dir or CFG.LLM_HISTORY_DIR)
    return os.path.abspath(
        os.path.join(base, ARCHIVE_DIR_NAME, f"{safe_segment(session_name)}.md")
    )


def archive_verbatim_history(
    messages: "list[ModelMessage]",
    *,
    session_name: str,
    history_dir: str | None = None,
    tokens: int | None = None,
) -> str | None:
    """Append *messages* to the conversation's archive; return the path.

    Never raises: failing to archive must not fail the turn that needed the
    summary. Returns ``None`` when there was nothing to write or the write
    failed.
    """
    if not messages:
        return None
    path = verbatim_archive_path(session_name, history_dir)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        is_new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as stream:
            if is_new:
                stream.write(_file_header(session_name))
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
        "rewritten or removed. Read this file when a summary lacks the detail you\n"
        "need.\n"
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
        lines.append("")
    return "\n".join(lines)


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
