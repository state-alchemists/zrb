"""Best-effort filesystem snapshot taken before each AI turn."""

from __future__ import annotations

import logging

from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.snapshot.manager import SnapshotManager

logger = logging.getLogger(__name__)


async def take_pre_turn_snapshot(
    snapshot_manager: SnapshotManager | None,
    history_manager: AnyHistoryManager | None,
    session_name: str,
    user_message: str,
    timestamp: str,
) -> None:
    """Snapshot the filesystem, recording the message count so a rewind can
    restore history to a consistent state. Failures are logged, never raised:
    the turn must proceed regardless."""
    if snapshot_manager is None:
        return
    try:
        label = user_message[:80].replace("\n", " ").strip()
        messages = (
            history_manager.load(session_name) if history_manager is not None else []
        )
        await snapshot_manager.take_snapshot(
            f"{timestamp}: {label}", message_count=len(messages)
        )
    except Exception as snap_err:
        logger.warning(f"Snapshot skipped: {snap_err}")
