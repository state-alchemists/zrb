"""Volatile per-turn runtime state, rendered into a ``<live-context>`` block.

`render_live_context` builds the block the latest user message carries;
`previous_git_baseline` and `render_carried_context` read back what an earlier
turn already reported, and `LIVE_CONTEXT_ANCHOR` is the cached system prompt's
description of the format. The other modules here hold its parts — the
rendering and the per-turn providers — and the names below are the public
surface, unchanged from the module this replaced.
"""

from .context import (
    LIVE_CONTEXT_ANCHOR,
    previous_git_baseline,
    render_carried_context,
    render_live_context,
    render_live_context_async,
)

__all__ = [
    "LIVE_CONTEXT_ANCHOR",
    "previous_git_baseline",
    "render_carried_context",
    "render_live_context",
    "render_live_context_async",
]
