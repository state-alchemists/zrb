"""Naming convention and on-disk layout for a delegated sub-agent's
persisted conversation.

Single source of truth for the `{parent_session}-sub-{agent_name}-{agent_id}`
shape `zrb.llm.tool.delegate.run_agent_task` derives for every completed
delegation (Item 4, Phase A), and for where those transcripts live on disk:
`{LLM_HISTORY_DIR}/subagent/{agent_type}/`, separate from ordinary
main-agent conversations (which stay flat in the history root) so a history
listing/backup/prune never mixes the two. Kept stdlib-only and
dependency-free so both the delegate tool (which formats the name) and
consumers that only ever *parse* it — the web session lister
(`runner.chat.chat_session_manager`), the web resume router
(`runner.chat.chat_api_route`), the CLI TUI's persona-swap-on-`/load`
(Phase D), and `FileHistoryManager` (which resolves the layout) — can import
it without dragging in delegate.py's heavy transitive imports (pydantic_ai et
al.) just to recognize a name shape.

Delegated files written before the `subagent/<agent-type>/` layout shipped
still live flat in the history root; consumers read those legacy files as a
fallback rather than migrating them (no surprise disk writes).
"""

from __future__ import annotations

import os
import re

# The subdirectory under LLM_HISTORY_DIR that holds delegated transcripts.
SUBAGENT_HISTORY_SUBDIR = "subagent"

# Greedy backtracking on the two `.+` groups resolves to the rightmost
# "-sub-" marker, which is correct as long as no agent/session name contains
# that literal substring as its own delimiter — an acceptable best-effort
# limit for a listing/parsing feature, not a hard parser.
_DELEGATED_SESSION_PATTERN = re.compile(
    r"^(?P<parent>.+)-sub-(?P<agent_name>.+)-(?P<agent_id>[0-9a-f]{8})$"
)


def format_delegated_session_name(
    parent_session_id: str, agent_name: str, agent_id: str
) -> str:
    """The persisted conversation name for one delegated sub-agent run.

    An empty ``parent_session_id`` falls back to ``"default"``: the pattern's
    ``parent`` group requires at least one char, so an empty parent would
    otherwise produce a name ``parse_delegated_session`` can never parse back
    (neither listable nor resumable). The normal ambient-state path already
    substitutes ``"default"`` before any tool runs (`live_context.py`), but
    that's one caller's guarantee, not this function's — enforced here too so
    every caller, current or future, gets a name that round-trips.
    """
    parent_session_id = parent_session_id.strip() or "default"
    return f"{parent_session_id}-sub-{agent_name}-{agent_id}"


def parse_delegated_session(base_name: str) -> tuple[str, str] | None:
    """``(parent_session_id, agent_name)`` if *base_name* is a delegated
    sub-agent conversation's name, else ``None`` for an ordinary session."""
    match = _DELEGATED_SESSION_PATTERN.match(base_name)
    if not match:
        return None
    return match.group("parent"), match.group("agent_name")


def subagent_history_directories(history_dir: str) -> list[str]:
    """The directories that can hold delegated transcripts: the history root
    itself (legacy flat files written before the subdirectory layout) plus
    every ``subagent/{agent_type}/`` directory."""
    return [history_dir] + subagent_only_directories(history_dir)


def subagent_only_directories(history_dir: str) -> list[str]:
    """Every ``subagent/{agent_type}/`` directory, excluding the flat history
    root.

    Unlike ``subagent_history_directories``, this never includes the history
    root — the root is also where ordinary (non-delegated) sessions live, and
    a session name that merely *looks* delegated (matches
    ``parse_delegated_session``'s shape) is not actually one. Reads/listings
    can afford that ambiguity (worst case: a mislabeled listing entry); a
    caller that *deletes* files past a retention count cannot — so pruning
    uses this narrower list instead.
    """
    dirs: list[str] = []
    root = os.path.join(history_dir, SUBAGENT_HISTORY_SUBDIR)
    try:
        with os.scandir(root) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    dirs.append(entry.path)
    except OSError:
        pass
    return dirs
