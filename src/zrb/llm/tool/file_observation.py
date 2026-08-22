"""Run-scoped tracking of which files' current content has been observed.

`write_file(mode="w")` blindly truncates an existing file regardless of
whether the current agent run has ever seen its current content. This module
lets it refuse instead: `record_observed` is called after any Read, Write, or
Edit that produces the file's full current content; `check_observed` compares
that record against what's on disk right before a `mode="w"` overwrite.

Keyed by `get_current_agent_run_scope()` — the session name for a top-level
conversation (stable across its turns), but a fresh per-delegation id for a
sub-agent (see that ContextVar's docstring in `agent/run/runner.py`). Not
keyed by session alone: a delegated sub-agent starts with an empty
`message_history` and hasn't seen what its parent or a sibling sub-agent
observed, so sharing one bucket per session would let it blindly overwrite a
file it never itself read. Not a raw `ContextVar` holding this dict either —
a `ContextVar` only propagates within one asyncio task's context tree, so a
value a sub-agent's task `.set()`s would never reach its parent or siblings;
keying a plain dict by the (already correctly `ContextVar`-scoped) run id
sidesteps that, mirroring `plan.py::TodoManager`'s own keyed-dict pattern for
the same class of state. In-memory only, no disk persistence: a process
restart forcing one fresh Read before the next overwrite is the safe
default, not a gap worth engineering around.
"""

from __future__ import annotations

import hashlib

from zrb.llm.agent.run.runtime_state import get_current_agent_run_scope

# run_scope -> {abs_path: content_hash}
_observed: dict[str, dict[str, str]] = {}


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="surrogateescape")).hexdigest()


def record_observed(abs_path: str, content: str) -> None:
    """Record `content` as this agent run's current knowledge of `abs_path`.

    Call after any operation that ends up knowing the file's full current
    content: a successful Read, or a successful Write/Edit (using the
    content as it now stands on disk, not just the part that changed) —
    so an immediate follow-up Write/Edit on the same path never needs a
    fresh Read in between.
    """
    scope = get_current_agent_run_scope()
    _observed.setdefault(scope, {})[abs_path] = _hash(content)


def check_observed(abs_path: str) -> str | None:
    """Return a blocking error string if `abs_path` wasn't observed as its
    current content in this agent run; `None` if the overwrite may proceed.

    Only meaningful for a destructive overwrite of an *existing* file — the
    caller should skip this for a new file or a non-destructive append.
    """
    scope = get_current_agent_run_scope()
    recorded = _observed.get(scope, {}).get(abs_path)
    if recorded is None:
        return (
            f"Error: {abs_path} has not been read in this session.\n"
            "[SYSTEM SUGGESTION]: Read it first to see its current content, "
            "then retry the write."
        )
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            current = f.read()
    except Exception as e:
        return (
            f"Error: Could not verify the current content of {abs_path}: {e}.\n"
            "[SYSTEM SUGGESTION]: Investigate the read failure before "
            "overwriting the file."
        )
    if _hash(current) != recorded:
        return (
            f"Error: {abs_path} has changed since it was last read in this "
            "session.\n"
            "[SYSTEM SUGGESTION]: Read it again to see the current content, "
            "then retry the write if you still want to overwrite it."
        )
    return None


def clear_observed() -> None:
    """Clear all recorded state. A test-isolation seam — production code
    never needs this; per-scope buckets just persist for the process
    lifetime, same no-eviction posture as `TodoManager`.
    """
    _observed.clear()
