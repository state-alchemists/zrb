"""Appending and splitting the trailing ``<live-context>`` block of a user turn.

The two functions are inverses and have no dependencies, so the engine, the
history formatter, replay and the web chat all share them from here instead of
reaching into ``prompt/``.
"""

from __future__ import annotations

import re
from typing import Any

# `append_live_context` always appends the block last, after "\n\n" (or bare).
_LIVE_CONTEXT_BLOCK_RE = re.compile(
    r"\n\n(<live-context>.*</live-context>)\s*\Z", re.DOTALL
)


def append_live_context(prompt_content: Any, live_context: str) -> Any:
    """Append the ``<live-context>`` block to the end of the current user turn.

    Accepts a ``str``, a multimodal ``list`` or ``None``; a falsy
    *live_context* is a no-op. Inverse of ``split_live_context``.
    """
    if not live_context:
        return prompt_content
    if prompt_content is None:
        return live_context
    if isinstance(prompt_content, str):
        return f"{prompt_content}\n\n{live_context}"
    if isinstance(prompt_content, list):
        return [*prompt_content, live_context]
    return prompt_content


def split_live_context(content: str) -> tuple[str, str | None]:
    """Split a trailing ``<live-context>`` block off a stored user message for display.

    Returns ``(message_text, live_context_block)``; the block is ``None`` (and
    *content* unchanged) when there is none.
    """
    if not content or "<live-context>" not in content:
        return content, None
    match = _LIVE_CONTEXT_BLOCK_RE.search(content)
    if not match:
        # No leading blank line (e.g. the block was the entire prompt).
        idx = content.find("<live-context>")
        if content[idx:].rstrip().endswith("</live-context>"):
            return content[:idx].rstrip(), content[idx:].rstrip()
        return content, None
    return content[: match.start()].rstrip(), match.group(1)
