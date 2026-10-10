"""Name shape and on-disk layout of a delegated sub-agent's conversation.

Names are `{parent_session}-sub-{agent_name}-{agent_id}`; transcripts live in
`{LLM_HISTORY_DIR}/subagent/{agent_type}/`, with legacy flat files in the
history root read as a fallback. Stdlib-only so name parsers need not import
the delegate tool's heavy dependencies.
"""

from __future__ import annotations

import os
import re

# The subdirectory under LLM_HISTORY_DIR that holds delegated transcripts.
SUBAGENT_HISTORY_SUBDIR = "subagent"

# Greedy `.+` resolves to the rightmost "-sub-"; best-effort if a name
# contains that substring.
_DELEGATED_SESSION_PATTERN = re.compile(
    r"^(?P<parent>.+)-sub-(?P<agent_name>.+)-(?P<agent_id>[0-9a-f]{8})$"
)


def format_delegated_session_name(
    parent_session_id: str, agent_name: str, agent_id: str
) -> str:
    """The persisted conversation name for one delegated sub-agent run.

    An empty ``parent_session_id`` becomes ``"default"`` so the name still
    round-trips through ``parse_delegated_session``.
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


def parse_delegated_agent_id(base_name: str) -> str | None:
    """The 8-hex agent id of a delegated sub-agent conversation name, else ``None``."""
    match = _DELEGATED_SESSION_PATTERN.match(base_name)
    return match.group("agent_id") if match else None


def subagent_history_directories(history_dir: str) -> list[str]:
    """The directories that can hold delegated transcripts: the history root
    itself (legacy flat files written before the subdirectory layout) plus
    every ``subagent/{agent_type}/`` directory."""
    return [history_dir] + subagent_only_directories(history_dir)


def subagent_only_directories(history_dir: str) -> list[str]:
    """Every ``subagent/{agent_type}/`` directory, excluding the history root.

    Pruning uses this: an ordinary session in the root may merely look
    delegated, and must never be deleted as one.
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
